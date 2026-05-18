// Render the results screen given a result payload.

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
    card.innerHTML = `
      <div class="q">Part ${a.question_part} · ${renderQuestionText(a)}</div>
      <div class="meta">${a.word_count} words · ${a.duration_sec.toFixed(1)}s</div>
      <div class="t">${a.transcript || '(no transcript)'}</div>
      <audio controls preload="none" src="${a.audio_url}"></audio>
    `;
    answersList.appendChild(card);
  });
}
