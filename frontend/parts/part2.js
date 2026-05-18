export function renderPart2(prompt, visualEl, promptTextEl) {
  visualEl.innerHTML = '';
  promptTextEl.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'pic-card';
  card.innerHTML = `<div class="emoji">${prompt.data.picture.emoji || '🖼️'}</div><div class="label">${prompt.data.picture.label}</div>`;
  visualEl.appendChild(card);

  const qs = document.createElement('div');
  qs.className = 'prompt-questions';
  prompt.data.questions.forEach((q, i) => {
    const qd = document.createElement('div');
    qd.className = 'q';
    qd.dataset.num = String(i + 1);
    qd.textContent = q;
    qs.appendChild(qd);
  });
  promptTextEl.appendChild(qs);
}
