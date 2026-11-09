#!/usr/bin/env python3
"""FastAPI wrapper around the hanzi-stroke-courseware skill pipeline.

Endpoints:
    GET  /                              minimal HTML info page
    GET  /health                        {"ok": true}
    POST /generate                      start a generation job, returns job_id
    GET  /jobs/{job_id}                 job status and file links when done
    GET  /jobs/{job_id}/files/{name}    download lesson.html or lesson.pptx

The heavy lifting is done by the skill scripts in
<repo>/skills/hanzi-stroke-courseware/scripts, located relative to this
file, and run as subprocesses with the same interpreter. Nothing is copied.

Set the COURSEWARE_API_KEY environment variable to require an X-API-Key
header on POST /generate. When it is unset the API runs open, which is
meant for local use and the pre launch verification phase only.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse

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

app = FastAPI(title='Wentao Chinese Courseware API', version='0.1.0')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)

_jobs = {}
_jobs_lock = threading.Lock()
_run_slots = threading.Semaphore(2)


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


# ---------------------------------------------------------------- routes

INFO_PAGE = """<!DOCTYPE html>
<html lang="zh">
<head><meta charset="utf-8"><title>Wentao Chinese Courseware API</title></head>
<body>
<h1>文韬中文课件生成 API</h1>
<p>POST a word list, get back an interactive HTML lesson page and a PPTX deck
with stroke order animations, a tracing quiz and matching games.</p>
<h2>Endpoints</h2>
<ul>
  <li>GET /health &mdash; health check</li>
  <li>POST /generate &mdash; start a job. Body: {"title": optional,
      "words": [{"ch": "永", "py": "yǒng", "mean": "永远 · forever"}],
      "game_chars": optional}</li>
  <li>GET /jobs/{job_id} &mdash; job status and download links</li>
  <li>GET /jobs/{job_id}/files/lesson.html &mdash; the HTML lesson</li>
  <li>GET /jobs/{job_id}/files/lesson.pptx &mdash; the PPTX deck</li>
</ul>
<h2>Data and licenses</h2>
<p>Stroke order data comes from Make Me a Hanzi and is used under the
Arphic Public License. The full license text lives in the repository at
skills/hanzi-stroke-courseware/references/ARPHICPL.TXT.
The Hanzi Writer animation library is MIT licensed.</p>
</body>
</html>
"""


@app.get('/', response_class=HTMLResponse)
def index():
    return INFO_PAGE


@app.get('/health')
def health():
    return {'ok': True}


@app.post('/generate')
async def generate(request: Request):
    api_key = os.environ.get('COURSEWARE_API_KEY')
    if api_key and request.headers.get('x-api-key') != api_key:
        raise HTTPException(401, 'missing or wrong X-API-Key header')
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(422, 'request body must be valid JSON')
    spec = validate_payload(body)

    cleanup_old_jobs()
    job_id = uuid.uuid4().hex[:12]
    job_dir = os.path.join(JOBS_ROOT, job_id)
    os.makedirs(job_dir, exist_ok=True)
    with _jobs_lock:
        _jobs[job_id] = {'status': 'running', 'error': None,
                         'started': time.time(), 'elapsed_sec': None}
    threading.Thread(target=run_job, args=(job_id, spec), daemon=True).start()
    return {'job_id': job_id, 'status': 'running'}


@app.get('/jobs/{job_id}')
def job_status(job_id: str):
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(404, f'unknown job {job_id}')
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
def job_file(job_id: str, name: str):
    if name not in ALLOWED_FILES:
        raise HTTPException(404, f'only lesson.html and lesson.pptx are served, not {name!r}')
    path = os.path.join(JOBS_ROOT, job_id, name)
    if not os.path.isfile(path):
        raise HTTPException(404, 'file not found, the job may still be running or unknown')
    return FileResponse(path, media_type=ALLOWED_FILES[name], filename=name)
