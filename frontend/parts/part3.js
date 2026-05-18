export function renderPart3(prompt, visualEl, promptTextEl) {
  visualEl.innerHTML = '';
  promptTextEl.innerHTML = '';

  const card = document.createElement('div');
  card.className = 'topic-card';

  const h = document.createElement('h3');
  h.textContent = prompt.data.topic;
  card.appendChild(h);

  const grid = document.createElement('div');
  grid.className = 'bullets-grid';

  const forCol = document.createElement('div');
  forCol.className = 'bullets-col for';
  forCol.innerHTML = '<h4>For</h4>';
  const forUl = document.createElement('ul');
  prompt.data.for_bullets.forEach((b) => {
    const li = document.createElement('li');
    li.textContent = b;
    forUl.appendChild(li);
  });
  forCol.appendChild(forUl);

  const againstCol = document.createElement('div');
  againstCol.className = 'bullets-col against';
  againstCol.innerHTML = '<h4>Against</h4>';
  const aUl = document.createElement('ul');
  prompt.data.against_bullets.forEach((b) => {
    const li = document.createElement('li');
    li.textContent = b;
    aUl.appendChild(li);
  });
  againstCol.appendChild(aUl);

  grid.appendChild(forCol);
  grid.appendChild(againstCol);
  card.appendChild(grid);
  visualEl.appendChild(card);

  promptTextEl.innerHTML =
    '<p class="muted small">Pick <strong>2 points from each side</strong> and give a balanced argument. Reach a conclusion.</p>';
}
