# Multilevel Speaking Trainer

A local-first web app that simulates the **Speaking** section of the **Uzbekistan National Multilevel English exam** (Milliy Sertifikat / Ko'p darajali test, administered by BMBA). It walks you through the three exam parts at the exact official timings, records your answers, transcribes them in the browser, and grades the session with **Google Gemini (free tier)** against the four official CEFR-aligned criteria.

Designed for one user (you), running on a laptop or a free PaaS. **No paid APIs required.**

## What it costs to run: $0

- **Transcription** uses the browser's built-in **Web Speech API** (Chrome, Edge, Safari) — runs entirely on your device, no upload, no key needed.
- **Grading and question generation** use **Google Gemini Flash** — free tier on Google AI Studio gives you ~1500 requests per day with no credit card.

## Get a free Google AI API key

1. Open <https://aistudio.google.com/apikey>
2. Sign in with any Google account
3. Click "Create API key" → copy it
4. Paste it into `.env` as `GOOGLE_API_KEY=...`

That's the only key you need.

## Quick start (local)

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env, set GOOGLE_API_KEY=...
uvicorn backend.main:app --reload
```

Open <http://localhost:8000>. The first time you start a session your browser will ask for microphone permission — say yes.

> Note: the Web Speech API needs Chrome / Edge / Safari. Firefox doesn't support it yet.

### Run with Docker

```bash
GOOGLE_API_KEY=your-key docker compose up --build
```

## Access from a phone

`MediaRecorder` and the Web Speech API both require **HTTPS** (or `localhost`). Three options:

1. **Same WiFi + ngrok on your laptop** — fastest. Run `uvicorn ...` on your laptop, then in another terminal run `ngrok http 8000` (free account at ngrok.com). Open the `https://...ngrok-free.app` URL on your phone.
2. **Deploy to Render.com (free)** — push the repo, create a Web Service from Docker, set `GOOGLE_API_KEY` env var, deploy. You get a permanent `https://*.onrender.com` URL.
3. **Local network + Chrome dev flag** — Chrome on Android can be told to treat your laptop's LAN IP as a secure origin via `chrome://flags/#unsafely-treat-insecure-origin-as-secure`. Add `http://<laptop-ip>:8000`, restart Chrome. (Don't do this for anything sensitive.)

## Architecture

```
┌─────────────────────────┐         ┌──────────────────────────┐
│  Browser                │         │  FastAPI                 │
│                         │  HTTP   │                          │
│  • MediaRecorder        ├────────▶│  /api/sessions/start     │
│  • Web Speech API       │         │  /api/audio/transcribe   │
│    (free transcript)    │         │  /api/sessions/.../finish│
│  • Chart.js (progress)  │         │  /api/sessions/.../result│
│                         │         │  /api/questions/generate │
└─────────────────────────┘         │  /api/progress           │
                                    └──────┬───────────────────┘
                                           │
                          ┌────────────────┴───────────────┐
                          ▼                                ▼
                     SQLite DB                Google Gemini Flash
                  (questions,                 (free tier — grading
                   sessions,                   + question generation)
                   answers,
                   grades)
```

Transcription happens entirely in the browser. The backend just stores the transcript text + the audio blob (for playback on the results screen) and asks Gemini to grade the transcript.

## Exam format implemented

| Part | What | Prep | Speaking | Prompts |
|------|------|------|----------|---------|
| 1    | Personal questions + picture compare | 5s each | 30s each | 3 personal + 1 compare set |
| 2    | Long turn on a topic | 60s | 120s | 1 set (3 questions in one answer) |
| 3    | For/against debate | 60s | 120s | 1 topic, pick 2+2 bullets |

**Scoring:** four criteria each 0–9 → raw 0–36 → converted to 0–75.
- 0–37 → below B1
- 38–50 → B1
- 51–64 → **B2** (target band)
- 65–75 → C1

Pronunciation is **estimated from the transcript** (Gemini doesn't hear audio). The UI flags this.

## Adding questions manually

Edit JSON files in `backend/seed_data/` then delete `multilevel.db` and restart. Seed only runs if the table is empty.

## Generating new questions via the API

```bash
curl -X POST http://localhost:8000/api/questions/generate \
     -H "Content-Type: application/json" \
     -d '{"part": 3, "count": 5}'
```

## Project layout

```
backend/
  main.py              FastAPI app + lifespan
  config.py            Pydantic Settings (env)
  database.py          SQLAlchemy engine + session factory
  models.py            Question / Session / Answer / Grade
  schemas.py           Pydantic request/response models
  routers/             sessions, questions, audio, scoring, progress
  services/
    llm_client.py      Gemini REST client (httpx)
    claude_grader.py   Grader: prompt + JSON parse + band logic
    claude_generator.py Question generator
    question_bank.py   Seed + random selection
  seed_data/*.json
frontend/
  index.html + styles.css + app.js + recorder.js + timer.js + api.js
  parts/part1.js, part2.js, part3.js, results.js
tests/                 pytest suite (mocked LLM)
```

The `claude_*.py` filenames are kept for backwards compatibility with earlier commits; the implementations now call Gemini.

## Development

```bash
python -m pytest tests/ -v
uvicorn backend.main:app --reload
# http://localhost:8000/docs
```

## Notes

- **Audio retention**: WebM blobs persist in `./audio_uploads/{session_id}/`. No TTL; sweep manually if disk grows.
- **Pronunciation scoring** is an estimate from transcript patterns. For real pronunciation feedback you'd need an audio-native model.
- **Single user.** No auth.
- **CORS** is locked to `localhost`. Update `backend/main.py` if deploying.

## Reference

- BMBA exam description: <https://bmba.uz/uz/menu/milliy-sertifikat>
- Free Gemini API: <https://aistudio.google.com/apikey>
