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

// Tracks whether an exam session is currently running so the topbar nav
// can't accidentally reset the user back to the home screen mid-test.
let sessionActive = false;
let activeSession = null;

function setSessionActive(on) {
  sessionActive = on;
  document.body.classList.toggle('in-session', on);
}

function goto(name, payload) {
  const fn = routes[name];
  if (!fn) return;
  speech.cancel();
  fn(payload);
}

document.addEventListener('click', (e) => {
  const t = e.target.closest('[data-route]');
  if (!t) return;
  e.preventDefault();
  if (sessionActive) {
    const ok = window.confirm('Leave the test in progress? Your answers so far will be lost.');
    if (!ok) return;
    abortActiveSession();
  }
  goto(t.dataset.route);
});

function abortActiveSession() {
  if (!activeSession) return;
  activeSession.aborted = true;
  try { activeSession.recorder?.release(); } catch (e) { /* */ }
  activeSession = null;
  setSessionActive(false);
}

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
  document.querySelectorAll('[data-start]').forEach((btn) => {
    btn.addEventListener('click', () => {
      const parts = btn.dataset.start.split(',').map(Number);
      runSession(parts);
    });
  });
}

// --- Exam loop ---------------------------------------------------------

async function runSession(parts) {
  if (sessionActive) return;

  let session;
  try {
    session = await api.startSession(parts);
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

  const ctx = { aborted: false, recorder };
  activeSession = ctx;
  setSessionActive(true);

  // Build a flat queue of prompts annotated with part index
  const queue = [];
  session.parts.forEach((pp) => {
    pp.prompts.forEach((p) => queue.push({ part: pp.part, prompt: p }));
  });

  let qIdx = 0;
  let lastPart = null;

  for (let i = 0; i < queue.length; i++) {
    if (ctx.aborted) return;
    const { part, prompt } = queue[i];

    if (lastPart !== null && lastPart !== part) {
      await runIntermission(lastPart, part);
      if (ctx.aborted) return;
    }
    lastPart = part;

    const partTotalInSession = queue.filter((x) => x.part === part).length;
    const indexInPart = queue.slice(0, i + 1).filter((x) => x.part === part).length;

    await runPrompt({
      ctx,
      recorder,
      sessionId: session.session_id,
      part,
      prompt,
      questionIdx: qIdx,
      counter: `Part ${part} · ${indexInPart} / ${partTotalInSession}`,
      progress: (i + 1) / queue.length,
    });
    if (ctx.aborted) return;
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
    activeSession = null;
    setSessionActive(false);
    goto('home');
    return;
  }

  activeSession = null;
  setSessionActive(false);

  mountTemplate('tpl-results');
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

async function runPrompt({ ctx, recorder, sessionId, part, prompt, questionIdx, counter, progress }) {
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
    phaseEl, timerEl, skipBtn, ctx,
  });
  if (ctx?.aborted) return;

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
    phaseEl, timerEl, skipBtn, ctx,
  });

  recIndicator.classList.add('hidden');
  const { blob, durationSec } = await recorder.stop();
  if (ctx?.aborted) return;
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

function runPhase({ label, cls, seconds, phaseEl, timerEl, skipBtn, ctx }) {
  return new Promise((resolve) => {
    phaseEl.textContent = label;
    phaseEl.className = `phase-label ${cls}`;
    timerEl.className = `timer mono ${cls}`;
    timerEl.textContent = formatTime(seconds);

    let abortPoll = null;
    const cleanup = () => {
      skipBtn.removeEventListener('click', skip);
      if (abortPoll) { clearInterval(abortPoll); abortPoll = null; }
    };

    const cd = createCountdown({
      seconds,
      onTick: (r) => { timerEl.textContent = formatTime(r); },
      onDone: () => { cleanup(); resolve(); },
    });

    function skip() {
      cd.stop();
      cleanup();
      resolve();
    }
    skipBtn.addEventListener('click', skip);

    // Bail out of the countdown if the session is aborted from elsewhere.
    if (ctx) {
      abortPoll = setInterval(() => {
        if (ctx.aborted) {
          cd.stop();
          cleanup();
          resolve();
        }
      }, 200);
    }

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

// --- Boot --------------------------------------------------------------

renderHome();
