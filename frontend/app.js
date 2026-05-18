// Main controller, routing, and the exam loop.

import { api } from '/static/api.js';
import { createCountdown, formatTime } from '/static/timer.js';
import { AudioRecorder } from '/static/recorder.js';
import { renderPart1 } from '/static/parts/part1.js';
import { renderPart2 } from '/static/parts/part2.js';
import { renderPart3 } from '/static/parts/part3.js';
import { renderResults } from '/static/parts/results.js';
import { speech, promptToSpeech } from '/static/speech.js';

const main = document.getElementById('main');
const toast = document.getElementById('toast');

function showToast(msg, ms = 4500) {
  toast.textContent = msg;
  toast.classList.remove('hidden');
  clearTimeout(showToast._t);
  showToast._t = setTimeout(() => toast.classList.add('hidden'), ms);
}

function mountTemplate(id) {
  const tpl = document.getElementById(id);
  main.innerHTML = '';
  main.appendChild(tpl.content.cloneNode(true));
  return main;
}

function delay(ms) { return new Promise((r) => setTimeout(r, ms)); }

// --- Routing -----------------------------------------------------------

const routes = {
  home: renderHome,
  progress: renderProgress,
};

function goto(name, payload) {
  const fn = routes[name];
  if (!fn) return;
  speech.cancel();
  fn(payload);
}

document.addEventListener('click', (e) => {
  const t = e.target.closest('[data-route]');
  if (t) {
    e.preventDefault();
    goto(t.dataset.route);
  }
});

// Voice-over master toggle in the topbar.
function syncAudioToggle() {
  const btn = document.getElementById('audio-toggle');
  if (!btn) return;
  const on = btn.querySelector('.audio-icon-on');
  const off = btn.querySelector('.audio-icon-off');
  if (!on || !off) return;
  on.classList.toggle('hidden', !speech.enabled);
  off.classList.toggle('hidden', speech.enabled);
  btn.classList.toggle('muted', !speech.enabled);
  btn.title = speech.enabled ? 'Voice-over on — click to mute' : 'Voice-over off — click to enable';
}
document.addEventListener('DOMContentLoaded', syncAudioToggle);
syncAudioToggle();
document.getElementById('audio-toggle')?.addEventListener('click', () => {
  speech.toggle();
  syncAudioToggle();
});

// --- Home --------------------------------------------------------------

function renderHome() {
  mountTemplate('tpl-home');
  const customToggle = main.querySelector('#use-custom-only');
  const statsEl = main.querySelector('#custom-toggle-stats');
  refreshCustomStats(statsEl, customToggle);

  document.querySelectorAll('[data-start]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const parts = btn.dataset.start.split(',').map(Number);
      runSession(parts, { useCustomOnly: !!customToggle?.checked });
    });
  });
}

async function refreshCustomStats(statsEl, toggle) {
  try {
    const stats = await api.customStats();
    if (statsEl) statsEl.textContent = `${stats.total} uploaded`;
    if (toggle) {
      toggle.disabled = stats.total === 0;
      if (stats.total === 0) toggle.checked = false;
    }
  } catch {
    if (statsEl) statsEl.textContent = '—';
  }
}

// --- Exam loop ---------------------------------------------------------

async function runSession(parts, opts = {}) {
  let session;
  try {
    session = await api.startSession(parts, opts);
  } catch (e) {
    showToast(e.detail || e.message || 'Failed to start session');
    return;
  }

  if (!AudioRecorder.isSupported()) {
    showToast('Microphone recording is not supported in this browser.');
    return;
  }

  const recorder = new AudioRecorder();
  try {
    await recorder.ensureStream();
  } catch (e) {
    showToast('Microphone permission denied. Cannot continue.');
    return;
  }

  // Build a flat queue of prompts annotated with part index
  const queue = [];
  session.parts.forEach((pp) => {
    pp.prompts.forEach((p) => queue.push({ part: pp.part, prompt: p }));
  });

  let qIdx = 0;
  let lastPart = null;

  for (let i = 0; i < queue.length; i++) {
    const { part, prompt } = queue[i];

    if (lastPart !== null && lastPart !== part) {
      await runIntermission(lastPart, part);
    }
    lastPart = part;

    const partTotalInSession = queue.filter((x) => x.part === part).length;
    const indexInPart = queue.slice(0, i + 1).filter((x) => x.part === part).length;

    await runPrompt({
      recorder,
      sessionId: session.session_id,
      part,
      prompt,
      questionIdx: qIdx,
      counter: `Part ${part} · ${indexInPart} / ${partTotalInSession}`,
      progress: (i + 1) / queue.length,
    });
    qIdx += 1;
  }

  recorder.release();

  // Transcribe + grade screen
  mountTemplate('tpl-grading');
  let result;
  try {
    await api.finishSession(session.session_id);
    result = await api.getResult(session.session_id);
  } catch (e) {
    showToast(e.detail || e.message || 'Grading failed. You can retry from the progress page.');
    await delay(2500);
    goto('home');
    return;
  }

  mountTemplate('tpl-results');
  document.querySelectorAll('[data-route]').forEach((el) => {
    el.addEventListener('click', () => goto(el.dataset.route));
  });
  renderResults(main, result);
}

async function runIntermission(fromPart, toPart) {
  mountTemplate('tpl-intermission');
  const h = main.querySelector('h2');
  const count = main.querySelector('.big-countdown');
  h.textContent = `Part ${fromPart} complete · Part ${toPart} starting`;
  for (let s = 5; s > 0; s--) {
    count.textContent = String(s);
    await delay(1000);
  }
}

function renderPromptVisuals(prompt, visualEl, promptTextEl) {
  if (prompt.type === 'personal' || prompt.type === 'compare') renderPart1(prompt, visualEl, promptTextEl);
  else if (prompt.type === 'long_turn') renderPart2(prompt, visualEl, promptTextEl);
  else if (prompt.type === 'for_against') renderPart3(prompt, visualEl, promptTextEl);
}

async function runPrompt({ recorder, sessionId, part, prompt, questionIdx, counter, progress }) {
  mountTemplate('tpl-part-active');
  const counterEl = main.querySelector('.part-counter');
  const progressEl = main.querySelector('.progress-fill');
  const phaseEl = main.querySelector('.phase-label');
  const timerEl = main.querySelector('.timer');
  const visualEl = main.querySelector('.visual-area');
  const promptTextEl = main.querySelector('.prompt-text');
  const recIndicator = main.querySelector('.recording-indicator');
  const liveEl = main.querySelector('.live-transcript');
  const skipBtn = main.querySelector('.skip-btn');
  const replayBtn = main.querySelector('.replay-btn');

  counterEl.textContent = counter;
  progressEl.style.width = `${Math.round(progress * 100)}%`;
  renderPromptVisuals(prompt, visualEl, promptTextEl);

  const spokenText = promptToSpeech(prompt);
  if (replayBtn) {
    replayBtn.addEventListener('click', () => { speech.speak(spokenText); });
    replayBtn.classList.toggle('hidden', !spokenText || !speech.supported);
  }

  // Speak the prompt as preparation begins.
  if (spokenText) speech.speak(spokenText);

  // Phase 1: preparation
  await runPhase({
    label: 'Preparation',
    cls: 'prep',
    seconds: prompt.prep_sec,
    phaseEl, timerEl, skipBtn,
  });

  // Phase 2: recording. Stop any voice-over so it doesn't bleed into the microphone.
  speech.cancel();
  recIndicator.classList.remove('hidden');
  if (replayBtn) replayBtn.classList.add('hidden');
  liveEl.textContent = '';
  let lastTranscript = '';
  await recorder.start({ onLiveText: (t) => { lastTranscript = t; liveEl.textContent = t; } });

  await runPhase({
    label: 'Speaking',
    cls: 'rec',
    seconds: prompt.rec_sec,
    phaseEl, timerEl, skipBtn,
  });

  recIndicator.classList.add('hidden');
  const { blob, durationSec } = await recorder.stop();
  const finalTranscript = (recorder.liveText || lastTranscript || '').trim();
  const prosody = recorder.prosodySummary || null;

  // Show uploading screen
  mountTemplate('tpl-transcribing');

  try {
    await api.uploadAudio({
      blob,
      transcript: finalTranscript,
      prosody,
      sessionId,
      questionId: prompt.question_id,
      questionIdx,
      durationSec,
    });
  } catch (e) {
    showToast(e.detail || e.message || 'Transcription failed for this answer.');
    // continue anyway — we still let the user finish the session
  }
}

function runPhase({ label, cls, seconds, phaseEl, timerEl, skipBtn }) {
  return new Promise((resolve) => {
    phaseEl.textContent = label;
    phaseEl.className = `phase-label ${cls}`;
    timerEl.className = `timer mono ${cls}`;
    timerEl.textContent = formatTime(seconds);

    const cd = createCountdown({
      seconds,
      onTick: (r) => { timerEl.textContent = formatTime(r); },
      onDone: () => {
        skipBtn.removeEventListener('click', skip);
        resolve();
      },
    });

    function skip() {
      cd.stop();
      skipBtn.removeEventListener('click', skip);
      resolve();
    }
    skipBtn.addEventListener('click', skip);
    cd.start();
  });
}

// --- Progress page -----------------------------------------------------

async function renderProgress() {
  mountTemplate('tpl-progress');
  let sessions;
  try {
    sessions = await api.progress();
  } catch (e) {
    showToast(e.detail || e.message || 'Failed to load progress');
    return;
  }

  const tbody = main.querySelector('.sessions-table tbody');
  tbody.innerHTML = '';
  sessions.slice().reverse().forEach((s) => {
    const tr = document.createElement('tr');
    const date = new Date(s.started_at).toLocaleDateString();
    tr.innerHTML = `
      <td>${date}</td>
      <td>${s.parts.join(', ')}</td>
      <td>${s.score_75 ?? '—'}</td>
      <td>${s.band ?? '—'}</td>
    `;
    tbody.appendChild(tr);
  });

  const completed = sessions.filter((s) => s.score_75 != null);
  if (completed.length === 0) return;

  // Wait for Chart.js to load (it's deferred from CDN)
  const tryDraw = () => {
    if (!window.Chart) return setTimeout(tryDraw, 100);
    const canvas = document.getElementById('progress-chart');
    if (!canvas) return;
    new window.Chart(canvas, {
      type: 'line',
      data: {
        labels: completed.map((s) => new Date(s.started_at).toLocaleDateString()),
        datasets: [{
          label: 'Score / 75',
          data: completed.map((s) => s.score_75),
          borderColor: '#d4a259',
          backgroundColor: 'rgba(212,162,89,0.15)',
          tension: 0.25,
          fill: true,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        scales: {
          y: { min: 0, max: 75, ticks: { color: '#8b93a8' }, grid: { color: '#232a40' } },
          x: { ticks: { color: '#8b93a8' }, grid: { color: '#232a40' } },
        },
        plugins: { legend: { labels: { color: '#e6e8ee' } } },
      },
    });
  };
  tryDraw();
}

// --- Upload modal ------------------------------------------------------

const TEMPLATE_JSON = {
  part1_personal: [
    { text: "Tell me about a teacher who influenced you." },
    { text: "How do you usually spend your weekends?" }
  ],
  part1_compare: [
    {
      pic1: { emoji: "🍳", label: "Cooking at home" },
      pic2: { emoji: "🍽️", label: "Eating at a restaurant" },
      questions: [
        "What is happening in each picture?",
        "Which would you choose on a weekend, and why?"
      ]
    }
  ],
  part2: [
    {
      picture: { emoji: "🎮", label: "A favourite game" },
      questions: [
        "Tell me about a game you enjoy playing.",
        "Why do you find it interesting?",
        "How can games be useful for learning?"
      ]
    }
  ],
  part3: [
    {
      topic: "Should homework be banned at primary school?",
      for_bullets: [
        "More time for sport and family",
        "Less stress for young children",
        "Encourages curiosity, not duty",
        "Teachers can cover everything in class"
      ],
      against_bullets: [
        "Builds study habits early",
        "Reinforces what was learnt in class",
        "Prepares pupils for higher grades",
        "Parents can see what is being studied"
      ]
    }
  ]
};

let uploadModalEl = null;

function openUploadModal() {
  if (uploadModalEl) return;
  const tpl = document.getElementById('tpl-upload-modal');
  uploadModalEl = tpl.content.firstElementChild.cloneNode(true);
  document.body.appendChild(uploadModalEl);

  const close = () => {
    uploadModalEl?.remove();
    uploadModalEl = null;
    // Refresh home stats if home is mounted
    const t = document.getElementById('custom-toggle-stats');
    const c = document.getElementById('use-custom-only');
    if (t) refreshCustomStats(t, c);
  };

  uploadModalEl.querySelector('.modal-close').addEventListener('click', close);
  uploadModalEl.addEventListener('click', (e) => { if (e.target === uploadModalEl) close(); });
  document.addEventListener('keydown', function escClose(e) {
    if (e.key === 'Escape' && uploadModalEl) { close(); document.removeEventListener('keydown', escClose); }
  });

  refreshUploadStats();

  uploadModalEl.querySelector('#upload-file').addEventListener('change', async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const resultEl = uploadModalEl.querySelector('#upload-result');
    resultEl.classList.remove('hidden', 'error', 'success');
    resultEl.textContent = 'Uploading…';
    try {
      const res = await api.uploadQuestions(file);
      const total = res.inserted.total;
      const parts = [];
      if (res.inserted.part1_personal) parts.push(`${res.inserted.part1_personal} personal`);
      if (res.inserted.part1_compare) parts.push(`${res.inserted.part1_compare} compare`);
      if (res.inserted.part2) parts.push(`${res.inserted.part2} long-turn`);
      if (res.inserted.part3) parts.push(`${res.inserted.part3} debate`);
      let msg = total ? `Added ${total} question${total === 1 ? '' : 's'} (${parts.join(', ')}).` : 'No valid questions found.';
      if (res.skipped) msg += ` Skipped ${res.skipped} invalid.`;
      resultEl.classList.add(total ? 'success' : 'error');
      resultEl.innerHTML = msg + (res.errors?.length ? `<details><summary>Show ${res.errors.length} issue${res.errors.length === 1 ? '' : 's'}</summary><ul>${res.errors.map((x) => `<li>${escapeHtml(x)}</li>`).join('')}</ul></details>` : '');
      refreshUploadStats();
    } catch (err) {
      resultEl.classList.add('error');
      resultEl.textContent = err.detail || err.message || 'Upload failed';
    } finally {
      e.target.value = '';
    }
  });

  uploadModalEl.querySelector('#download-template').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(TEMPLATE_JSON, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'my-questions-template.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  uploadModalEl.querySelector('#clear-custom').addEventListener('click', async () => {
    if (!confirm('Delete all uploaded questions? This cannot be undone.')) return;
    try {
      const res = await api.clearCustomQuestions();
      const resultEl = uploadModalEl.querySelector('#upload-result');
      resultEl.classList.remove('hidden', 'error');
      resultEl.classList.add('success');
      resultEl.textContent = `Removed ${res.deleted} question${res.deleted === 1 ? '' : 's'}.`;
      refreshUploadStats();
    } catch (err) {
      showToast(err.detail || err.message || 'Failed to clear');
    }
  });
}

async function refreshUploadStats() {
  if (!uploadModalEl) return;
  try {
    const stats = await api.customStats();
    uploadModalEl.querySelectorAll('[data-key]').forEach((el) => {
      el.textContent = stats[el.dataset.key] ?? 0;
    });
  } catch {
    /* ignore */
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}

document.addEventListener('click', (e) => {
  if (e.target.closest('#open-upload')) {
    e.preventDefault();
    openUploadModal();
  }
});

// --- Boot --------------------------------------------------------------

renderHome();
