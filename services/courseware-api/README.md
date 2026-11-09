# Courseware API

A FastAPI wrapper around the `hanzi-stroke-courseware` skill pipeline. It
runs the four skill scripts (`fetch_data.py`, `build_html.py`,
`gen_gifs.py`, `build_pptx.py`) as subprocesses and serves the finished
lesson files. The skill scripts are located relative to this service
inside the repo, so the service only works as part of the
`wentao-chinese-skills` repository checkout.

## Endpoints

- `GET /` — minimal HTML info page with the endpoint list and data
  attribution.
- `GET /health` — returns `{"ok": true}`.
- `POST /generate` — starts a generation job and returns
  `{"job_id": ..., "status": "running"}` right away.
  Body: `{"title": "optional", "words": [{"ch": "永", "py": "yǒng",
  "mean": "永远 · forever"}], "game_chars": ["optional"]}`.
  `words` must hold 1 to 20 entries, each `ch` exactly one CJK character,
  `py` and `mean` non-empty strings of at most 60 characters. Invalid
  input gets a 422 with the specific reason.
- `GET /jobs/{job_id}` — `{"status": "running" | "done" | "error",
  "elapsed_sec": ...}` plus, when done, `files` with the two download
  paths, and `error` when the job failed.
- `GET /jobs/{job_id}/files/lesson.html` and
  `GET /jobs/{job_id}/files/lesson.pptx` — the generated files. Only
  these two file names are served.

Jobs run in background threads, at most 2 at a time (extra jobs queue).
Job files live in the system temp directory under `courseware-jobs/` and
jobs older than 2 hours are cleaned up when a new job starts. Job state
is kept in memory, so a service restart forgets running jobs.

## Environment variables

- `COURSEWARE_API_KEY` — when set, `POST /generate` requires the header
  `X-API-Key` to match it exactly (401 otherwise). `GET /` and
  `GET /health` stay open. When unset, no key is checked. Leave it unset
  only for local use and the pre launch verification phase.

## Local run

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8791
```

Run it from this directory or pass `--app-dir` pointing here (see the
Render start commands below).

## Render deployment

The service is deployed from the `wentao-chinese-skills` GitHub repo as
a Python web service. Pick one of the two layouts.

### Root Directory = repo root (empty)

- Build Command: `pip install -r services/courseware-api/requirements.txt`
- Start Command: `uvicorn app.main:app --app-dir services/courseware-api --host 0.0.0.0 --port $PORT`

### Root Directory = `services/courseware-api`

- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

Set `COURSEWARE_API_KEY` in the Render environment once the service
leaves the verification phase. Free tier instances spin down when idle,
so the first request after a quiet period is slow while the instance
wakes up and the generation pipeline itself takes a while on top.

## Data and licenses

Stroke order data comes from Make Me a Hanzi and is used under the
Arphic Public License. The full license text lives in the repository at
`skills/hanzi-stroke-courseware/references/ARPHICPL.TXT`.
The Hanzi Writer animation library is MIT licensed.
