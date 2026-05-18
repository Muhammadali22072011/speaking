# Multilevel Speaking Trainer

A local-first web app that simulates the **Speaking** section of the **Uzbekistan National Multilevel English exam** (Milliy Sertifikat / Ko‘p darajali test, administered by BMBA). It walks you through the three exam parts at the exact official timings, records your answers, transcribes them via OpenAI Whisper, and grades the session with Anthropic Claude against the four official CEFR-aligned criteria.

Designed for one user (you), running on a laptop. No accounts, no cloud.

---

## Quick start

```bash
pip install -r requirements.txt
cp .env.example .env
# then edit .env to fill in your real API keys
uvicorn backend.main:app --reload
```

Open <http://localhost:8000>.

You will need:
- `ANTHROPIC_API_KEY` — used for grading + question generation (model: `claude-opus-4-7`)
- `OPENAI_API_KEY` — used for speech transcription (model: `whisper-1`)

The SQLite database (`multilevel.db`) and audio files (`./audio_uploads/`) are created on first run.

### Run with Docker

```bash
docker compose up --build
```

(Make sure your `.env` exports `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`.)

---

## Architecture

```
┌─────────────────────────┐         ┌──────────────────────────┐
│  Browser (frontend/)    │         │  FastAPI (backend/)      │
│                         │  HTTP   │                          │
│  • MediaRecorder        ├────────▶│  /api/sessions/start     │
│  • Web Speech (live)    │         │  /api/audio/transcribe   │
│  • Chart.js (progress)  │         │  /api/sessions/.../finish│
│                         │         │  /api/sessions/.../result│
└─────────────────────────┘         │  /api/questions/generate │
                                    │  /api/progress           │
                                    └──────┬───────────────────┘
                                           │
                          ┌────────────────┼────────────────┐
                          ▼                ▼                ▼
                     SQLite DB     OpenAI Whisper    Anthropic Claude
                  (questions,      (transcription)   (grading +
                   sessions,                          question gen.)
                   answers,
                   grades)
```

---

## Exam format implemented

| Part | What | Prep | Speaking | Prompts per part |
|------|------|------|----------|------------------|
| 1    | Personal questions + picture compare | 5 s each | 30 s each | 3 personal + 1 compare set (2 questions) |
| 2    | Long turn on a topic (3 questions in one answer) | 60 s | 120 s | 1 set |
| 3    | For/against debate (pick 2 + 2 bullets) | 60 s | 120 s | 1 topic |

**Scoring:** four criteria each 0–9 → raw 0–36 → converted to 0–75.
- 0–37 → below B1
- 38–50 → B1
- 51–64 → **B2** (target band)
- 65–75 → C1

Pronunciation is **estimated from the transcript** (Claude doesn't hear the audio) and the UI flags this.

---

## Adding questions manually

Edit the seed JSON files in `backend/seed_data/`:
- `part1_personal.json` — 17 questions seeded; each `{"text": "..."}`
- `part1_compare.json` — 9 sets; pair of emoji+label + two compare questions
- `part2.json` — 11 sets; one picture + three questions (personal → analytical → abstract)
- `part3.json` — 11 for/against topics; 4 bullets per side

After editing, delete `multilevel.db` and restart — seed runs only if the table is empty.

## Generating new questions via the API

```bash
curl -X POST http://localhost:8000/api/questions/generate \
     -H "Content-Type: application/json" \
     -d '{"part": 3, "count": 5}'
```

Returns the newly-inserted question IDs. The next session you start may include them.

---

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
    whisper.py         OpenAI Whisper wrapper
    claude_grader.py   Claude grader prompt + JSON parse + band logic
    claude_generator.py Claude question generator
    question_bank.py   Seed + random selection
  seed_data/*.json
frontend/
  index.html + styles.css + app.js + recorder.js + timer.js + api.js
  parts/part1.js, part2.js, part3.js, results.js
tests/                 pytest suite (mocked Claude + Whisper)
```

---

## Development

```bash
# Run tests
python -m pytest tests/ -v

# Iterate on backend with auto-reload
uvicorn backend.main:app --reload

# View API docs
open http://localhost:8000/docs
```

## Notes & limitations

- **Audio retention:** uploaded WebM blobs persist in `./audio_uploads/{session_id}/`. There's no TTL; add a cron job or sweep manually if disk grows.
- **Pronunciation scoring is an estimate** based on transcript artefacts (word repetition, mis-spellings Whisper produces for hesitations, etc.). For an authoritative pronunciation score you'd need an audio-native model (e.g. SpeechAce). The UI is honest about this.
- **Single user.** No auth, no multi-tenancy. The DB is yours.
- **CORS** is locked to `localhost`.

## Reference

- BMBA exam description: <https://bmba.uz/uz/menu/milliy-sertifikat>
- CEFR band descriptors: Council of Europe CEFR Companion Volume (2020)
