"""MCP (Model Context Protocol) front end for the courseware service.

This mounts a FastMCP server (Streamable HTTP transport) at /mcp on the
main FastAPI app, so any MCP capable AI client (Claude, ChatGPT,
Cursor, ...) can generate Wentao Chinese courseware by calling tools
instead of the REST API. It is a thin layer over the exact same job
pipeline: tools create jobs with the shared start_job() and read them
back with job_snapshot(), both injected from app.main to avoid a
circular import.

Two tools, both asynchronous in spirit because one lesson takes tens
of seconds to a couple of minutes on the free tier:

- generate_courseware: validate the word list and start a job,
  returns the job_id right away.
- get_courseware: poll a job; when done it returns the download URLs
  for lesson.html and lesson.pptx (the normal REST file endpoints).

Auth: every /mcp request, the initialize handshake included, must
carry the programmatic API key, either as an X-API-Key header or as
Authorization: Bearer <key>, matching COURSEWARE_API_KEY. The web
session login is not accepted here. When COURSEWARE_API_KEY is not
set at all the endpoint is open, mirroring the REST fallback used for
local development.
"""
import os
import secrets
import time

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field


class WordInput(BaseModel):
    """One entry of the word list, same shape as the REST /generate API."""

    ch: str = Field(description='单个汉字，例如 永')
    py: str = Field(description='拼音，例如 yǒng')
    mean: str = Field(description='释义，例如 永远 · forever')


class ToolResult(BaseModel):
    """Shared result shape of both tools.

    A typed model (instead of a bare dict) makes FastMCP emit an
    output schema and return structured content, which MCP clients
    handle more reliably than a JSON blob in a text block. Fields
    that do not apply to a given answer stay None.
    """

    status: str = Field(description='running、done 或 error')
    message: str = Field(description='给人看的说明')
    job_id: str | None = None
    html_url: str | None = None
    pptx_url: str | None = None


class McpApiKeyMiddleware:
    """Pure ASGI middleware guarding the whole MCP app with the API key.

    A plain ASGI wrapper (not BaseHTTPMiddleware) so the streaming
    responses of the Streamable HTTP transport pass through untouched.
    """

    def __init__(self, asgi_app):
        self.asgi_app = asgi_app

    async def __call__(self, scope, receive, send):
        if scope.get('type') == 'http':
            expected = os.environ.get('COURSEWARE_API_KEY')
            if expected:
                headers = {
                    k.decode('latin-1').lower(): v.decode('latin-1')
                    for k, v in scope.get('headers', [])
                }
                provided = headers.get('x-api-key')
                if provided is None:
                    auth = headers.get('authorization', '')
                    if auth.lower().startswith('bearer '):
                        provided = auth[7:].strip()
                ok = provided is not None and secrets.compare_digest(
                    provided.encode('utf-8'), expected.encode('utf-8'))
                if not ok:
                    body = b'{"detail": "missing or invalid API key"}'
                    await send({
                        'type': 'http.response.start',
                        'status': 401,
                        'headers': [
                            (b'content-type', b'application/json'),
                            (b'content-length', str(len(body)).encode()),
                        ],
                    })
                    await send({'type': 'http.response.body', 'body': body})
                    return
        await self.asgi_app(scope, receive, send)


def build_mcp(start_job, validate_payload, job_snapshot):
    """Create the FastMCP server.

    The three callables are the job pipeline pieces from app.main.
    Returns (session_manager, asgi_app): the caller must mount
    asgi_app at /mcp and run session_manager.run() inside the host
    app's lifespan, because a mounted sub-application never receives
    the lifespan scope itself.
    """
    mcp = FastMCP(
        'wentao-courseware',
        instructions=(
            'Generate Chinese lesson courseware for Wentao Chinese: call '
            'generate_courseware with the lesson word list (each word needs '
            'ch 汉字, py 拼音, mean 释义), then poll get_courseware with the '
            'returned job_id until it is done and hand the teacher the '
            'html_url and pptx_url download links.'
        ),
        # No server side sessions: every request is self contained,
        # which keeps the endpoint working across free tier restarts
        # while a client is polling a long running job.
        stateless_http=True,
        # FastMCP auto enables DNS rebinding protection with a
        # loopback only host allowlist when its host setting is a
        # loopback address (the default). Mounted into this service
        # the real Host is the public hostname, which that allowlist
        # would reject, so turn the check off explicitly: the
        # endpoint is guarded by the API key instead.
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=False),
        # The host app mounts this at /mcp, so inside the sub app the
        # endpoint must live at the root to end up at exactly /mcp.
        streamable_http_path='/',
    )

    @mcp.tool()
    def generate_courseware(words: list[WordInput],
                            title: str | None = None,
                            game_chars: list[str] | None = None) -> ToolResult:
        """生成一课汉字课件（带笔顺动画的 HTML 和 PPT），异步模式。

        words 是生字表，1 到 20 个字，每项包含 ch（单个汉字）、
        py（拼音）、mean（释义）。title 是可选的课程标题。
        game_chars 可选，从 words 里挑最多 6 个字做翻牌配对游戏，
        不传就用默认。本工具只负责把任务发出去，立刻返回 job_id；
        课件生成要几十秒到两分钟，请随后用 get_courseware 查询。
        """
        body = {'words': [w.model_dump() for w in words]}
        if title is not None:
            body['title'] = title
        if game_chars is not None:
            body['game_chars'] = game_chars
        try:
            spec = validate_payload(body)
        except Exception as e:
            # validate_payload raises HTTPException with a human readable
            # detail; hand it back as a normal tool result so the calling
            # AI can fix its input and retry.
            return ToolResult(status='error',
                              message=str(getattr(e, 'detail', e)))
        job_id = start_job(spec, owner='api-key')
        return ToolResult(
            job_id=job_id,
            status='running',
            message='课件正在生成，通常需要几十秒到两分钟（免费版服务器较慢）。'
                    '请稍等片刻，再用 get_courseware 工具拿着这个 job_id 查询，'
                    '生成完成后会返回 HTML 和 PPTX 的下载地址。')

    @mcp.tool()
    def get_courseware(job_id: str) -> ToolResult:
        """查询 generate_courseware 发起的课件生成进度。

        status 为 running 时过一会儿再查；done 时返回 html_url 和
        pptx_url 两个下载地址（下载时也要带上同样的 API key 请求头）；
        error 时 message 里是失败原因。
        """
        job = job_snapshot(job_id)
        if job is None:
            return ToolResult(
                status='error',
                message=f'找不到 job {job_id}：id 不对，或者已经过期'
                        '（生成结果只保留 2 小时）。')
        if job['status'] == 'running':
            elapsed = round(time.time() - job['started'], 1)
            return ToolResult(
                status='running',
                message=f'还在生成中（已用 {elapsed} 秒），请过一会儿再查一次。')
        if job['status'] == 'error':
            return ToolResult(status='error',
                              message=f'生成失败：{job.get("error")}')
        base = os.environ.get('BASE_URL', '').rstrip('/')
        return ToolResult(
            status='done',
            message='课件生成好了。把下面两个下载地址给老师'
                    '（下载时也要带上同样的 API key 请求头）。',
            html_url=f'{base}/jobs/{job_id}/files/lesson.html',
            pptx_url=f'{base}/jobs/{job_id}/files/lesson.pptx')

    # streamable_http_app() lazily creates the session manager, so it
    # must be called before session_manager can be handed to the caller.
    asgi_app = mcp.streamable_http_app()
    return mcp.session_manager, McpApiKeyMiddleware(asgi_app)
