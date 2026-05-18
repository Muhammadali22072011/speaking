// Backend API wrappers

async function request(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) {
    let detail = '';
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch (e) {
      detail = await res.text();
    }
    const err = new Error(`API ${res.status}: ${detail}`);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  return res.json();
}

export const api = {
  startSession(parts) {
    return request('/api/sessions/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parts }),
    });
  },

  finishSession(sessionId) {
    return request(`/api/sessions/${sessionId}/finish`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
    });
  },

  getResult(sessionId) {
    return request(`/api/sessions/${sessionId}/result`);
  },

  progress() {
    return request('/api/progress');
  },

  uploadAudio({ blob, transcript, sessionId, questionId, questionIdx, durationSec }) {
    const fd = new FormData();
    fd.append('audio', blob, `${questionIdx}.webm`);
    fd.append('transcript', transcript || '');
    fd.append('session_id', sessionId);
    fd.append('question_id', questionId);
    fd.append('question_idx', questionIdx);
    fd.append('duration_sec', durationSec.toFixed(2));
    return request('/api/audio/transcribe', { method: 'POST', body: fd });
  },
};
