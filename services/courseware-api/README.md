# Courseware API + Web App

One FastAPI service that is the teacher facing web app
（文韬中文 · 课件工坊）, the generation API behind it, and an MCP
server for AI clients (see "MCP endpoint" below). It runs the four
`hanzi-stroke-courseware` skill scripts (`fetch_data.py`,
`build_html.py`, `gen_gifs.py`, `build_pptx.py`) as subprocesses and
serves the finished lesson files. The skill scripts are located
relative to this service inside the repo, so the service only works as
part of the `wentao-chinese-skills` repository checkout.

## Web app

- `GET /` — teachers land here. Logged out visitors get the landing
  page with a "用 Google 登录" button. Logged in teachers get the
  workshop page: a word list editor (add and remove rows, or paste a
  block of `字 拼音 释义` lines and parse it into the table), an
  optional lesson title, today's remaining free quota, a generate
  button, a progress readout while the job runs, and download buttons
  for the PPTX and the HTML lesson when it is done.
- `GET /auth/google/login` — starts the Google OAuth flow
  (scopes `openid email profile`, `prompt=select_account`, state kept
  in the session).
- `GET /auth/google/callback` — exchanges the code for tokens, reads
  the Google userinfo, and stores `{email, name, picture}` in the
  session.
- `GET /auth/logout` — clears the session.
- `GET /auth/dev` — local testing shortcut that logs in a fixed
  `dev@example.com` user. Only exists when `DEV_LOGIN=1`.
  **Never set `DEV_LOGIN` on Render or anywhere public: anyone who
  opens that URL is instantly logged in, no password asked.**

## API endpoints

- `GET /health` — returns `{"ok": true}`.
- `POST /generate` — starts a generation job and returns
  `{"job_id": ..., "status": "running"}` right away (web callers also
  get `quota_remaining`). Body: `{"title": "optional", "words":
  [{"ch": "永", "py": "yǒng", "mean": "永远 · forever"}],
  "game_chars": ["optional"]}`. `words` must hold 1 to 20 entries,
  each `ch` exactly one CJK character, `py` and `mean` non-empty
  strings of at most 60 characters. Invalid input gets a 422 with the
  specific reason.
- `GET /jobs/{job_id}` — `{"status": "running" | "done" | "error",
  "elapsed_sec": ...}` plus, when done, `files` with the two download
  paths, and `error` when the job failed.
- `GET /jobs/{job_id}/files/lesson.html` and
  `GET /jobs/{job_id}/files/lesson.pptx` — the generated files. Only
  these two file names are served.

Jobs run in background threads, at most 2 at a time (extra jobs queue).
Job files live in the system temp directory under `courseware-jobs/`
and jobs older than 2 hours are cleaned up when a new job starts. Job
state is kept in memory, so a service restart forgets running jobs.

## MCP endpoint

AI clients that speak the
[Model Context Protocol](https://modelcontextprotocol.io) (Claude,
ChatGPT, Cursor, and other MCP capable agents) can generate
courseware directly, without going through the web page or REST
calls. The endpoint is Streamable HTTP on the same service:

```
POST {BASE_URL}/mcp
```

It exposes exactly two tools, mirroring the REST flow:

- `generate_courseware` — arguments: `words` (required, the same
  `[{ch, py, mean}]` list as `POST /generate`), `title` (optional),
  `game_chars` (optional). A lesson takes tens of seconds to a couple
  of minutes, so the tool is asynchronous: it validates the input,
  starts a job and returns `{job_id, status: "running", message}`
  right away. Invalid input comes back as `status: "error"` with the
  specific reason in `message`, so the calling AI can fix and retry.
- `get_courseware` — argument: `job_id`. Returns `status: "running"`
  with an elapsed time while the job works, `status: "error"` with
  the failure reason, or `status: "done"` with `html_url` and
  `pptx_url`: absolute download URLs (built from `BASE_URL`) pointing
  at the normal REST file endpoints.

**Auth is the API key, same as REST**: every MCP request, including
the `initialize` handshake, must carry `X-API-Key: <key>` or
`Authorization: Bearer <key>` equal to `COURSEWARE_API_KEY`, or it
gets a 401. The Google web session is not accepted on this endpoint.
The file downloads behind `html_url` / `pptx_url` need the same key
header too (they are the REST endpoints above).

Client configuration example (for MCP hosts that accept a remote
server URL plus headers):

```json
{
  "mcpServers": {
    "wentao-courseware": {
      "url": "https://wentao-courseware-api.onrender.com/mcp",
      "headers": {
        "X-API-Key": "replace-with-the-courseware-api-key"
      }
    }
  }
}
```

The endpoint is stateless (no server side MCP sessions), so polling
keeps working even if the free tier instance restarted between the
two tool calls. Implementation: `app/mcp_server.py`, built on the
official `mcp` Python SDK (FastMCP, pinned to the v1 line in
`requirements.txt`), reusing the same validation and job pipeline as
REST.

## Who can call what (identities and quota)

`POST /generate`, `GET /jobs/{id}` and the file downloads accept two
identities:

- **API key** — header `X-API-Key` equal to `COURSEWARE_API_KEY`.
  The programmatic path: no login, **no daily quota**, and it can read
  every job (useful for debugging).
- **Web session** — a teacher logged in with Google. Each Google
  account gets `FREE_DAILY_LIMIT` generations per day (default 5);
  past that, `POST /generate` returns **429** with a plain language
  reason. Web users can only read their own jobs; asking for someone
  else's job id returns 404.

Every job records its owner (the account email, or `api-key`).

Quota counting is kept **in memory** on purpose for the free tier: it
resets when the process restarts and is per instance. That is accepted
for now; move it to a database when paid plans need exact accounting.

When `COURSEWARE_API_KEY` is **not set at all**, requests without a
session fall back to the API key identity (the original open mode).
That is meant for local development only. In production the key is
always set, so anonymous API calls get a 401 there. `GET /` and
`GET /health` are always open.

## Environment variables

- `COURSEWARE_API_KEY` — shared secret for the programmatic API path
  (see above).
- `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — Google OAuth client for
  the web login. Create it in Google Cloud Console as a Web
  application and register the redirect URI below. When either is
  missing the service still starts; the landing page just shows the
  login button as not configured.
- `BASE_URL` — public base URL of the service, no trailing slash,
  e.g. `https://wentao-courseware-api.onrender.com`. The OAuth
  redirect URI is `{BASE_URL}/auth/google/callback`; register exactly
  that in Google Cloud Console. When unset, the URL of the incoming
  request is used, which is fine locally.
- `SESSION_SECRET` — signing secret for the session cookie. Set a long
  random value in production; when unset, an ephemeral per process
  secret is used and restarts log everyone out.
- `FREE_DAILY_LIMIT` — free generations per Google account per day,
  default `5`.
- `DEV_LOGIN` — set to `1` to enable `/auth/dev` for local testing.
  **Never set this on Render.** See the warning above.

## Local run

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8791
```

Run it from this directory or pass `--app-dir` pointing here (see the
Render start commands below). For a Google free local session without
Google credentials:

```bash
DEV_LOGIN=1 SESSION_SECRET=dev-secret COURSEWARE_API_KEY=test \
  uvicorn app.main:app --port 8792
# then open http://127.0.0.1:8792/auth/dev
```

## Render deployment

The service is deployed from the `wentao-chinese-skills` GitHub repo as
a Python web service. Pick one of the two layouts.

### Root Directory = repo root (empty)

- Build Command: `pip install -r services/courseware-api/requirements.txt`
- Start Command: `uvicorn app.main:app --app-dir services/courseware-api --host 0.0.0.0 --port $PORT`

### Root Directory = `services/courseware-api`

- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set `COURSEWARE_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`,
`BASE_URL` and `SESSION_SECRET` in the Render environment for the web
launch. Never set `DEV_LOGIN`. Free tier instances spin down when
idle, so the first request after a quiet period is slow while the
instance wakes up, and the generation pipeline itself takes a while on
top (about 1 to 2 minutes for a full lesson on the free tier).

## Data and licenses

Stroke order data comes from Make Me a Hanzi and is used under the
Arphic Public License. The full license text lives in the repository at
`skills/hanzi-stroke-courseware/references/ARPHICPL.TXT`.
The Hanzi Writer animation library is MIT licensed.
