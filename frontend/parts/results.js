// Render the results screen given a result payload.

import { api } from '/static/api.js';
import { speech } from '/static/speech.js';

function renderQuestionText(answer) {
  const d = answer.question_data;
  if (answer.question_subtype === 'personal') return d.text || '';
  if (answer.question_subtype === 'compare') {
    return `Compare: ${d.pic1?.label} vs ${d.pic2?.label}`;
  }
  if (answer.question_subtype === 'long_turn') {
    return `${d.picture?.label}: ${(d.questions || []).join(' / ')}`;
  }
  if (answer.question_subtype === 'for_against') {
    return d.topic || '';
  }
  return '';
}

function attachC1SampleButton(card, answer) {
  if (answer.question_subtype !== 'for_against') return;
  if (!speech.supported) return;

  const wrap = document.createElement('div');
  wrap.className = 'c1-sample';

  const btn = document.createElement('button');
  btn.type = 'button';
  btn.className = 'c1-sample-btn';
  btn.innerHTML = '<span class="c1-icon">🔊</span><span class="c1-label">Hear a C1 example</span>';

  const textEl = document.createElement('div');
  textEl.className = 'c1-sample-text hidden';

  let cachedText = '';
  let playing = false;

  function setLabel(text, { busy = false, playing: isPlaying = false } = {}) {
    btn.querySelector('.c1-label').textContent = text;
    btn.disabled = busy;
    btn.classList.toggle('busy', busy);
    btn.classList.toggle('playing', isPlaying);
  }

  async function speakSample(text) {
    playing = true;
    setLabel('Stop', { playing: true });
    await speech.speak(text, { rate: 0.95 });
    playing = false;
    setLabel('Replay C1 example');
  }

  btn.addEventListener('click', async () => {
    if (playing) {
      speech.cancel();
      playing = false;
      setLabel(cachedText ? 'Replay C1 example' : 'Hear a C1 example');
      return;
    }
    if (cachedText) {
      speakSample(cachedText);
      return;
    }
    setLabel('Generating…', { busy: true });
    try {
      const res = await api.c1Sample(answer.question_id);
      cachedText = res.text || '';
    } catch (e) {
      setLabel('Try again', { busy: false });
      textEl.textContent = e.detail || e.message || 'Could not generate C1 example.';
      textEl.classList.remove('hidden');
      textEl.classList.add('error');
      return;
    }
    if (!cachedText) {
      setLabel('No sample available', { busy: false });
      return;
    }
    textEl.textContent = cachedText;
    textEl.classList.remove('hidden', 'error');
    speakSample(cachedText);
  });

  wrap.appendChild(btn);
  wrap.appendChild(textEl);
  card.appendChild(wrap);
}

export function renderResults(root, result) {
  const grade = result.grade;
  if (!grade) {
    root.querySelector('.score-number').textContent = '—';
    return;
  }

  root.querySelector('.score-number').textContent = String(grade.score_75);
  root.querySelector('.score-band').textContent = grade.band;

  const rows = root.querySelectorAll('.crit-row');
  rows.forEach((row) => {
    const key = row.dataset.key;
    if (key) {
      row.querySelector('.crit-score').textContent = (grade[key]).toFixed(1) + ' / 9';
    }
  });
  root.querySelector('.crit-row.total .crit-score').textContent =
    grade.raw_sum.toFixed(1) + ' / 36';

  // Feedback blocks
  const fb = root.querySelector('.feedback-body');
  fb.innerHTML = '';
  const order = [
    ['overall', 'Overall'],
    ['discourse', 'Discourse Management'],
    ['grammar', 'Grammar'],
    ['vocabulary', 'Vocabulary'],
    ['pronunciation', 'Pronunciation (estimated)'],
  ];
  order.forEach(([key, label]) => {
    if (!grade.feedback[key]) return;
    const block = document.createElement('div');
    block.className = 'fb-block';
    block.innerHTML = `<div class="fb-label">${label}</div><div>${grade.feedback[key]}</div>`;
    fb.appendChild(block);
  });

  // Tips
  const tipsList = root.querySelector('.tips-list');
  tipsList.innerHTML = '';
  (grade.feedback.improvement_tips || []).forEach((tip) => {
    const li = document.createElement('li');
    li.textContent = tip;
    tipsList.appendChild(li);
  });

  // Answers
  const answersList = root.querySelector('.answers-list');
  answersList.innerHTML = '';
  result.answers.forEach((a) => {
    const card = document.createElement('div');
    card.className = 'answer-card';
    const punctuated = a.punctuated_transcript || a.transcript || '';
    const showRaw = a.punctuated_transcript && a.transcript &&
                    a.punctuated_transcript.trim() !== a.transcript.trim();
    const metaBits = [`${a.word_count} words`, `${a.duration_sec.toFixed(1)}s`];
    if (a.prosody) {
      if (a.prosody.pitch_range_hz != null) {
        metaBits.push(`pitch ±${Math.round(a.prosody.pitch_range_hz)} Hz`);
      }
      if (a.prosody.pause_count != null) {
        metaBits.push(`${a.prosody.pause_count} pauses`);
      }
    }
    card.innerHTML = `
      <div class="q">Part ${a.question_part} · ${renderQuestionText(a)}</div>
      <div class="meta">${metaBits.join(' · ')}</div>
      <div class="t">${punctuated || '(no transcript)'}</div>
    `;
    if (a.intonation_note) {
      const note = document.createElement('div');
      note.className = 'intonation-note';
      note.innerHTML = `<span class="intonation-label">Intonation</span> ${a.intonation_note}`;
      card.appendChild(note);
    }
    if (showRaw) {
      const raw = document.createElement('details');
      raw.className = 'raw-transcript';
      raw.innerHTML = `<summary>Raw transcript</summary><div class="t raw">${a.transcript}</div>`;
      card.appendChild(raw);
    }
    const audio = document.createElement('audio');
    audio.controls = true;
    audio.preload = 'none';
    audio.src = a.audio_url;
    card.appendChild(audio);
    attachC1SampleButton(card, a);
    answersList.appendChild(card);
  });
}
