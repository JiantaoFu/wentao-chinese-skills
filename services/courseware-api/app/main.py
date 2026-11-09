#!/usr/bin/env python3
"""FastAPI app for Wentao Chinese lesson courseware: web UI plus API.

Routes:
    GET  /                              web app: landing page when logged
                                        out, workshop page when logged in
    GET  /health                        {"ok": true}
    GET  /auth/google/login             start Google OAuth
    GET  /auth/google/callback          Google OAuth callback
    GET  /auth/logout                   clear the session
    GET  /auth/dev                      local only login shortcut, only
                                        when DEV_LOGIN=1 (never in prod)
    POST /generate                      start a generation job
    GET  /jobs/{job_id}                 job status and file links
    GET  /jobs/{job_id}/files/{name}    download lesson.html or lesson.pptx

The heavy lifting is done by the skill scripts in
<repo>/skills/hanzi-stroke-courseware/scripts, located relative to this
file, and run as subprocesses with the same interpreter. Nothing is copied.

POST /generate accepts two identities:

- An X-API-Key header matching the COURSEWARE_API_KEY environment
  variable. This is the programmatic path: no login, no daily quota, and
  it can read every job (handy for debugging).
- A logged in web session (Google OAuth). Web users get a free daily
  quota of FREE_DAILY_LIMIT generations per Google account (default 5)
  and can only read their own jobs.

When COURSEWARE_API_KEY is not set at all, requests without a session
fall back to the API key identity, which keeps the original open local
mode working for development. In production the key is always set, so
anonymous calls get a 401 there.
"""
import datetime
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import urllib.parse
import urllib.request
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

try:
    from .web import landing_page, workshop_page
except ImportError:  # running as a loose module, not as the app package
    from web import landing_page, workshop_page

HERE = os.path.dirname(os.path.abspath(__file__))
SERVICE_DIR = os.path.dirname(HERE)                       # services/courseware-api
REPO_ROOT = os.path.dirname(os.path.dirname(SERVICE_DIR))  # repo root
SKILL_DIR = os.path.join(REPO_ROOT, 'skills', 'hanzi-stroke-courseware')
SCRIPTS_DIR = os.path.join(SKILL_DIR, 'scripts')

JOBS_ROOT = os.path.join(tempfile.gettempdir(), 'courseware-jobs')
JOB_TTL_SEC = 2 * 3600
STEP_TIMEOUT_SEC = 900

ALLOWED_FILES = {
    'lesson.html': 'text/html; charset=utf-8',
    'lesson.pptx': 'application/vnd.openxmlformats-officedocument.presentationml.presentation',
}

app = FastAPI(title='Wentao Chinese Courseware', version='0.2.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)
# Session cookie for the web login. Set SESSION_SECRET in production so
# sessions survive restarts; when it is unset an ephemeral per process
# secret is used and everyone is logged out on the next restart.
app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ.get('SESSION_SECRET') or secrets.token_hex(32),
)

_jobs = {}
_jobs_lock = threading.Lock()
_run_slots = threading.Semaphore(2)


# ---------------------------------------------------------------- quota

# Free daily quota per Google account, counted in memory only. The
# counts reset when the process restarts, which is accepted for the
# free tier (note in the README). Keys are account emails, values are
# (local date string, generations used that day).
_daily_usage = {}
_usage_lock = threading.Lock()


def free_daily_limit():
    try:
        return max(1, int(os.environ.get('FREE_DAILY_LIMIT', '5')))
    except ValueError:
        return 5


def _usage_today(email):
    today = datetime.date.today().isoformat()
    with _usage_lock:
        day, count = _daily_usage.get(email, (today, 0))
        return count if day == today else 0


def quota_remaining(email):
    return max(0, free_daily_limit() - _usage_today(email))


def quota_consume(email):
    """Take one generation slot. Return (True, remaining) or (False, 0)."""
    today = datetime.date.today().isoformat()
    with _usage_lock:
        day, count = _daily_usage.get(email, (today, 0))
        if day != today:
            count = 0
        if count >= free_daily_limit():
            return False, 0
        _daily_usage[email] = (today, count + 1)
        return True, free_daily_limit() - count - 1


# ---------------------------------------------------------------- identity

def _session_user(request):
    try:
        user = request.session.get('user')
    except Exception:
        return None
    return user if user and user.get('email') else None


def resolve_identity(request):
    """Return (kind, owner) for a request, or (None, None).

    kind 'api-key' means the programmatic identity (no quota, sees all
    jobs). kind 'user' means a logged in web user, owner is the email.
    See the module docstring for the exact fallback order.
    """
    api_key = os.environ.get('COURSEWARE_API_KEY')
    if api_key and request.headers.get('x-api-key') == api_key:
        return 'api-key', 'api-key'
    user = _session_user(request)
    if user:
        return 'user', user['email']
    if not api_key:
        return 'api-key', 'api-key'
    return None, None


# ---------------------------------------------------------------- validation

def _is_cjk(ch):
    return ('\u3400' <= ch <= '\u4dbf') or ('\u4e00' <= ch <= '\u9fff')


def validate_payload(body):
    """Return a cleaned spec dict, or raise HTTPException 422 with a reason."""
    if not isinstance(body, dict):
        raise HTTPException(422, 'request body must be a JSON object')

    title = body.get('title')
    if title is not None:
        if not isinstance(title, str) or not title.strip():
            raise HTTPException(422, 'title must be a non-empty string when given')
        if len(title) > 60:
            raise HTTPException(422, 'title is longer than 60 characters')

    words = body.get('words')
    if words is None:
        raise HTTPException(422, 'words is required')
    if not isinstance(words, list):
        raise HTTPException(422, 'words must be an array')
    if not (1 <= len(words) <= 20):
        raise HTTPException(422, f'words must hold 1 to 20 entries, got {len(words)}')

    clean_words = []
    for i, w in enumerate(words):
        if not isinstance(w, dict):
            raise HTTPException(422, f'words[{i}] must be an object with ch, py and mean')
        ch = w.get('ch')
        if not isinstance(ch, str) or len(ch) != 1:
            raise HTTPException(422, f'words[{i}].ch must be exactly one character, got {ch!r}')
        if not _is_cjk(ch):
            raise HTTPException(422, f'words[{i}].ch {ch!r} is not a CJK character')
        for field in ('py', 'mean'):
            v = w.get(field)
            if not isinstance(v, str) or not v.strip():
                raise HTTPException(422, f'words[{i}].{field} must be a non-empty string')
            if len(v) > 60:
                raise HTTPException(422, f'words[{i}].{field} is longer than 60 characters')
        clean_words.append({'ch': ch, 'py': w['py'], 'mean': w['mean']})

    spec = {'words': clean_words}
    if title is not None:
        spec['title'] = title

    game_chars = body.get('game_chars')
    if game_chars is not None:
        if not isinstance(game_chars, list) or len(game_chars) > 6:
            raise HTTPException(422, 'game_chars must be an array of at most 6 characters')
        known = {w['ch'] for w in clean_words}
        for g in game_chars:
            if not isinstance(g, str) or len(g) != 1 or g not in known:
                raise HTTPException(
                    422, f'game_chars entry {g!r} must be one character taken from words')
        if game_chars:
            spec['game_chars'] = list(game_chars)
    return spec


# ---------------------------------------------------------------- jobs

def cleanup_old_jobs():
    """Drop job directories older than the TTL. Called when a job starts."""
    now = time.time()
    if not os.path.isdir(JOBS_ROOT):
        return
    for name in os.listdir(JOBS_ROOT):
        path = os.path.join(JOBS_ROOT, name)
        try:
            if os.path.isdir(path) and now - os.path.getmtime(path) > JOB_TTL_SEC:
                shutil.rmtree(path, ignore_errors=True)
                with _jobs_lock:
                    _jobs.pop(name, None)
        except OSError:
            pass


def run_step(job_id, step, argv):
    proc = subprocess.run(
        [sys.executable] + argv,
        capture_output=True, text=True, timeout=STEP_TIMEOUT_SEC)
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or '').strip().splitlines()
        detail = tail[-1] if tail else f'exit code {proc.returncode}'
        raise RuntimeError(f'{step} failed: {detail}')


def run_job(job_id, spec):
    job_dir = os.path.join(JOBS_ROOT, job_id)
    with _run_slots:
        try:
            words_path = os.path.join(job_dir, 'words.json')
            with open(words_path, 'w', encoding='utf-8') as f:
                json.dump(spec, f, ensure_ascii=False)
            data_dir = os.path.join(job_dir, 'data')
            gif_dir = os.path.join(job_dir, 'gifs')
            html_out = os.path.join(job_dir, 'lesson.html')
            pptx_out = os.path.join(job_dir, 'lesson.pptx')

            run_step(job_id, 'fetch_data', [
                os.path.join(SCRIPTS_DIR, 'fetch_data.py'),
                '--words', words_path, '--data-dir', data_dir])
            run_step(job_id, 'build_html', [
                os.path.join(SCRIPTS_DIR, 'build_html.py'),
                '--words', words_path, '--data-dir', data_dir, '--out', html_out])
            run_step(job_id, 'gen_gifs', [
                os.path.join(SCRIPTS_DIR, 'gen_gifs.py'),
                '--words', words_path, '--data-dir', data_dir, '--out-dir', gif_dir])
            run_step(job_id, 'build_pptx', [
                os.path.join(SCRIPTS_DIR, 'build_pptx.py'),
                '--words', words_path, '--data-dir', data_dir,
                '--gif-dir', gif_dir, '--out', pptx_out])

            for path in (html_out, pptx_out):
                if not os.path.isfile(path):
                    raise RuntimeError(f'expected output missing: {os.path.basename(path)}')
            with _jobs_lock:
                _jobs[job_id]['status'] = 'done'
                _jobs[job_id]['elapsed_sec'] = round(time.time() - _jobs[job_id]['started'], 1)
        except Exception as e:
            with _jobs_lock:
                _jobs[job_id]['status'] = 'error'
                _jobs[job_id]['error'] = str(e)
                _jobs[job_id]['elapsed_sec'] = round(time.time() - _jobs[job_id]['started'], 1)


# ---------------------------------------------------------------- google auth

def google_configured():
    return bool(os.environ.get('GOOGLE_CLIENT_ID')
                and os.environ.get('GOOGLE_CLIENT_SECRET'))


def dev_login_enabled():
    return os.environ.get('DEV_LOGIN') == '1'


def _base_url(request):
    configured = os.environ.get('BASE_URL')
    if configured:
        return configured.rstrip('/')
    return str(request.base_url).rstrip('/')


def _redirect_uri(request):
    return _base_url(request) + '/auth/google/callback'


def _http_post_form(url, fields):
    data = urllib.parse.urlencode(fields).encode()
    req = urllib.request.Request(url, data=data, method='POST')
    req.add_header('Content-Type', 'application/x-www-form-urlencoded')
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


def _http_get_json(url, access_token):
    req = urllib.request.Request(url)
    req.add_header('Authorization', f'Bearer {access_token}')
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode())


@app.get('/auth/google/login')
def google_login(request: Request):
    if not google_configured():
        return RedirectResponse('/?login_error=config', status_code=302)
    state = secrets.token_urlsafe(24)
    request.session['oauth_state'] = state
    params = {
        'client_id': os.environ['GOOGLE_CLIENT_ID'],
        'redirect_uri': _redirect_uri(request),
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'prompt': 'select_account',
    }
    url = 'https://accounts.google.com/o/oauth2/v2/auth?' + urllib.parse.urlencode(params)
    return RedirectResponse(url, status_code=302)


@app.get('/auth/google/callback')
def google_callback(request: Request, code: str = '', state: str = ''):
    expected = request.session.pop('oauth_state', None)
    if (not google_configured() or not code or not expected
            or not secrets.compare_digest(state, expected)):
        return RedirectResponse('/?login_error=failed', status_code=302)
    try:
        token = _http_post_form('https://oauth2.googleapis.com/token', {
            'code': code,
            'client_id': os.environ['GOOGLE_CLIENT_ID'],
            'client_secret': os.environ['GOOGLE_CLIENT_SECRET'],
            'redirect_uri': _redirect_uri(request),
            'grant_type': 'authorization_code',
        })
        info = _http_get_json(
            'https://openidconnect.googleapis.com/v1/userinfo',
            token['access_token'])
    except Exception:
        return RedirectResponse('/?login_error=failed', status_code=302)
    email = info.get('email')
    if not email:
        return RedirectResponse('/?login_error=failed', status_code=302)
    request.session['user'] = {
        'email': email,
        'name': info.get('name', ''),
        'picture': info.get('picture', ''),
    }
    return RedirectResponse('/', status_code=302)


@app.get('/auth/logout')
def logout(request: Request):
    request.session.clear()
    return RedirectResponse('/', status_code=302)


@app.get('/auth/dev')
def dev_login(request: Request):
    # LOCAL TESTING ONLY. Logs in a fixed fake user so the web flow can be
    # exercised without Google credentials. Never set DEV_LOGIN on Render
    # or anywhere public: anyone who finds this URL is instantly logged in.
    if not dev_login_enabled():
        raise HTTPException(404, 'not found')
    request.session['user'] = {
        'email': 'dev@example.com', 'name': 'Dev User', 'picture': '',
    }
    return RedirectResponse('/', status_code=302)


# ---------------------------------------------------------------- routes

_LOGIN_ERRORS = {
    'failed': '登录没有完成，请再试一次。',
    'config': '登录还没有配置好，请联系管理员。',
}


@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    user = _session_user(request)
    if user:
        return workshop_page(user, quota_remaining(user['email']), free_daily_limit())
    error = _LOGIN_ERRORS.get(request.query_params.get('login_error', ''))
    return landing_page(google_configured(), free_daily_limit(),
                        login_error=error, dev_login=dev_login_enabled())


@app.get('/health')
def health():
    return {'ok': True}


@app.post('/generate')
async def generate(request: Request):
    kind, owner = resolve_identity(request)
    if kind is None:
        raise HTTPException(401, 'log in first, or send a valid X-API-Key header')
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(422, 'request body must be valid JSON')
    spec = validate_payload(body)

    remaining = None
    if kind == 'user':
        ok, remaining = quota_consume(owner)
        if not ok:
            raise HTTPException(
                429, f'今天的免费生成次数已经用完了（每天 {free_daily_limit()} 次），明天再来吧。')

    cleanup_old_jobs()
    job_id = uuid.uuid4().hex[:12]
    job_dir = os.path.join(JOBS_ROOT, job_id)
    os.makedirs(job_dir, exist_ok=True)
    with _jobs_lock:
        _jobs[job_id] = {'status': 'running', 'error': None, 'owner': owner,
                         'started': time.time(), 'elapsed_sec': None}
    threading.Thread(target=run_job, args=(job_id, spec), daemon=True).start()
    out = {'job_id': job_id, 'status': 'running'}
    if remaining is not None:
        out['quota_remaining'] = remaining
    return out


def _authorize_job(request, job_id):
    """Return (kind, job dict) after identity and ownership checks."""
    kind, owner = resolve_identity(request)
    if kind is None:
        raise HTTPException(401, 'log in first, or send a valid X-API-Key header')
    with _jobs_lock:
        job = _jobs.get(job_id)
        snapshot = dict(job) if job is not None else None
    if snapshot is None:
        raise HTTPException(404, f'unknown job {job_id}')
    if kind == 'user' and snapshot.get('owner') != owner:
        # Do not reveal that another user owns this job.
        raise HTTPException(404, f'unknown job {job_id}')
    return kind, snapshot


@app.get('/jobs/{job_id}')
def job_status(request: Request, job_id: str):
    _kind, job = _authorize_job(request, job_id)
    out = {'job_id': job_id, 'status': job['status']}
    if job['status'] == 'error':
        out['error'] = job['error']
    if job['status'] == 'done':
        out['files'] = {
            'html': f'/jobs/{job_id}/files/lesson.html',
            'pptx': f'/jobs/{job_id}/files/lesson.pptx',
        }
    if job['elapsed_sec'] is not None:
        out['elapsed_sec'] = job['elapsed_sec']
    else:
        out['elapsed_sec'] = round(time.time() - job['started'], 1)
    return out


@app.get('/jobs/{job_id}/files/{name}')
def job_file(request: Request, job_id: str, name: str):
    if name not in ALLOWED_FILES:
        raise HTTPException(404, f'only lesson.html and lesson.pptx are served, not {name!r}')
    kind, owner = resolve_identity(request)
    if kind is None:
        raise HTTPException(401, 'log in first, or send a valid X-API-Key header')
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is not None and kind == 'user' and job.get('owner') != owner:
        raise HTTPException(404, 'file not found')
    if job is None and kind == 'user':
        # Unknown job (or state lost in a restart): web users may only
        # fetch files of jobs this process created for them.
        raise HTTPException(404, 'file not found')
    path = os.path.join(JOBS_ROOT, job_id, name)
    if not os.path.isfile(path):
        raise HTTPException(404, 'file not found, the job may still be running or unknown')
    return FileResponse(path, media_type=ALLOWED_FILES[name], filename=name)
