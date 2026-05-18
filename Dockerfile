FROM python:3.11-slim

WORKDIR /app

# System deps (ffmpeg helps with audio handling on the server side, even though
# Whisper API handles webm directly).
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

ENV DATABASE_URL=sqlite:///./data/multilevel.db
ENV AUDIO_UPLOAD_DIR=./data/audio_uploads
RUN mkdir -p /app/data/audio_uploads

EXPOSE 8000

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
