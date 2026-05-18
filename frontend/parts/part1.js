// Render visuals + prompt text for Part 1 prompts.

export function renderPart1(prompt, visualEl, promptTextEl) {
  visualEl.innerHTML = '';
  promptTextEl.innerHTML = '';

  if (prompt.type === 'personal') {
    promptTextEl.textContent = prompt.data.text;
    return;
  }

  if (prompt.type === 'compare') {
    const pair = document.createElement('div');
    pair.className = 'pic-pair';

    const card1 = document.createElement('div');
    card1.className = 'pic-card';
    card1.innerHTML = `<div class="emoji">${prompt.data.pic1.emoji || '🖼️'}</div><div class="label">${prompt.data.pic1.label}</div>`;

    const card2 = document.createElement('div');
    card2.className = 'pic-card';
    card2.innerHTML = `<div class="emoji">${prompt.data.pic2.emoji || '🖼️'}</div><div class="label">${prompt.data.pic2.label}</div>`;

    pair.appendChild(card1);
    pair.appendChild(card2);
    visualEl.appendChild(pair);

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
}
