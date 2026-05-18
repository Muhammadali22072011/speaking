# Multilevel Speaking Trainer

A local-first web app that simulates the **Speaking** section of the **Uzbekistan National Multilevel English exam** (Milliy Sertifikat / Ko'p darajali test, administered by BMBA). It walks you through the three exam parts at the exact official timings, records your answers, transcribes them with **Groq Whisper**, and grades the session with **Groq's free Llama-3.3-70B** against the four official CEFR-aligned criteria.

Designed for one user (you), running on a laptop or a free PaaS. **No paid APIs required.**

## What it costs to run: $0

- **Transcription** runs server-side on **Groq Whisper-large-v3** (the same free tier as the LLM, no extra key). The browser still captures a Web Speech API draft as a live preview during recording, but the saved transcript is whatever Whisper hears — much more accurate for non-native speakers. Whisper is given the wording of the current exam question as a vocabulary hint, which cuts mishears like "countersight" for "countryside" or "cause of living" for "cost of living". If the Whisper call fails, the browser draft is kept as a fallback.
- **Punctuation restoration & intonation note** use **Groq Llama-3.3-70B** with prosody hints (pause boundaries + pitch contour) extracted in-browser via the Web Audio API.
- **Grading and question generation** use **Groq Llama-3.3-70B** — generous free tier, no credit card.

## Get a free Groq API key

1. Open <https://console.groq.com/keys>
2. Sign in with Google or GitHub
3. Click **"Create API Key"** → copy the `gsk_...` value
4. Paste it into `.env` as `GROQ_API_KEY=...`

That's the only key you need.

## Quick start (local)

```bash
pip install -r requirements.txt
cp .env.example .env
# edit .env, set GROQ_API_KEY=gsk_...
uvicorn backend.main:app --reload
```

Open <http://localhost:8000>. First start asks for microphone permission — say yes.

> The Web Speech API needs Chrome / Edge / Safari. Firefox doesn't support it.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
notepad .env   # set GROQ_API_KEY=gsk_...
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

### Run with Docker

```bash
GROQ_API_KEY=gsk_... docker compose up --build
```

## Access from a phone

`MediaRecorder` and the Web Speech API both require **HTTPS** (or `localhost`). Three options:

1. **Same WiFi + ngrok on your laptop** — fastest. Run `uvicorn ...` on your laptop, in another terminal run `ngrok http 8000` (free account at ngrok.com). Open the `https://...ngrok-free.app` URL on your phone.
2. **Deploy to Render.com (free)** — push the repo, create a Web Service from Docker, set `GROQ_API_KEY` env var, deploy. Permanent `https://*.onrender.com` URL.
3. **Local network + Chrome dev flag** — Chrome on Android can be told to treat your laptop's LAN IP as a secure origin via `chrome://flags/#unsafely-treat-insecure-origin-as-secure`. Add `http://<laptop-ip>:8000`, restart Chrome.

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
                     SQLite DB                Groq Llama-3.3-70B
                  (questions,                 (free tier — grading
                   sessions,                   + question generation)
                   answers,
                   grades)
```

The browser records audio, shows a live Web Speech API draft to the user, and runs a Web Audio API pitch + pause analyser alongside to produce a prosody summary. The audio blob, the draft transcript and the prosody summary are uploaded together; the backend then re-transcribes the audio with Groq Whisper (biased by the question wording), prefers that result over the browser draft, asks Groq Llama to restore punctuation and write a short intonation note, and finally asks Groq Llama to grade the punctuated transcript with the prosody summary attached.

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

Pronunciation is **estimated from the transcript** (the LLM doesn't hear audio). The UI flags this.

On the results screen, every **Part 3 (for/against)** answer card has a **"🔊 Hear a C1 example"** button. It asks Groq Llama for a 130-160-word model answer to the exact same topic at C1 level — balanced arguments, complex grammar, sophisticated linkers — and reads it aloud through the browser's SpeechSynthesis voice (the same one used for the prompts). The result is also displayed under the button so you can read along.

## Adding questions manually

Edit JSON files in `backend/seed_data/`, delete `multilevel.db`, restart.

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
    llm_client.py      Groq Chat Completions client (httpx)
    claude_grader.py   Grader: prompt + JSON parse + band logic
    claude_generator.py Question generator
    question_bank.py   Seed + random selection
  seed_data/*.json
frontend/
  index.html + styles.css + app.js + recorder.js + timer.js + api.js
  parts/part1.js, part2.js, part3.js, results.js
tests/                 pytest suite (mocked LLM)
```

The `claude_*.py` filenames are kept for git history continuity; the implementations call Groq.

## Development

```bash
python -m pytest tests/ -v
uvicorn backend.main:app --reload
# http://localhost:8000/docs
```

## Notes

- **Audio retention**: WebM blobs persist in `./audio_uploads/{session_id}/`. No TTL.
- **Pronunciation scoring** is an estimate from transcript patterns.
- **Single user.** No auth.
- **CORS** locked to `localhost`. Update `backend/main.py` if deploying.

## Reference

- BMBA exam description: <https://bmba.uz/uz/menu/milliy-sertifikat>
- Free Groq API: <https://console.groq.com/keys>
