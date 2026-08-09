const names = { diagnosis: 'Diagnosis codes', procedure: 'Procedure codes', ndc: 'NDC codes' };
const setupPanel = document.querySelector('#setupPanel');
const message = document.querySelector('#message');
const searchButton = document.querySelector('.primary-button');
const normalizationPanel = document.querySelector('#normalizationPanel');
const termSuggestion = document.querySelector('#termSuggestion');
const termForm = document.querySelector('#termForm');
let pendingSearch = null;
let lastSearch = null;

document.querySelector('#setupToggle').addEventListener('click', () => setupPanel.classList.toggle('hidden'));
document.querySelector('#closeSetup').addEventListener('click', () => setupPanel.classList.add('hidden'));

async function refreshStatus() {
  const response = await fetch('/status');
  const status = await response.json();
  const cards = document.querySelector('#datasetCards');
  cards.innerHTML = Object.entries(status).map(([kind, data]) => `
    <article class="dataset-card ${data.loaded ? 'loaded' : ''}">
      <h3>${names[kind]}</h3>
      <p>${data.loaded ? `${data.rows.toLocaleString()} records loaded` : (data.error || `Waiting for ${data.filename}`)}</p>
      <label class="upload-label">${data.loaded ? 'Replace CSV' : 'Choose CSV'}
        <input type="file" accept=".csv,text/csv" data-kind="${kind}">
      </label>
    </article>`).join('');

  cards.querySelectorAll('input[type=file]').forEach(input => input.addEventListener('change', uploadDataset));
  if (Object.values(status).some(data => !data.loaded)) setupPanel.classList.remove('hidden');
}

async function uploadDataset(event) {
  const input = event.target;
  if (!input.files.length) return;
  const data = new FormData();
  data.append('kind', input.dataset.kind);
  data.append('file', input.files[0]);
  input.closest('label').textContent = 'Loading…';
  try {
    const response = await fetch('/upload', { method: 'POST', body: data });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    message.textContent = '';
  } catch (error) {
    message.textContent = error.message;
  }
  await refreshStatus();
}

document.querySelector('#searchForm').addEventListener('submit', async event => {
  event.preventDefault();
  const keyword = document.querySelector('#keyword').value.trim();
  const datasets = [...document.querySelectorAll('input[name=dataset]:checked')].map(input => input.value);
  message.textContent = '';
  normalizationPanel.classList.add('hidden');
  await runSearch(keyword, datasets);
});

function showNormalization(normalization, datasets) {
  pendingSearch = { abbreviation: normalization.abbreviation, datasets };
  document.querySelector('#normalizationHelp').textContent = `${normalization.abbreviation} has multiple possible meanings. Select the one you want to search for.`;
  document.querySelector('#normalizationOptions').innerHTML = normalization.options.map((option, index) => `
    <label><input type="radio" name="normalizedTerm" value="${escapeHtml(option)}" ${index === 0 ? 'checked' : ''}><span>${escapeHtml(option)}</span></label>
  `).join('');
  normalizationPanel.classList.remove('hidden');
  normalizationPanel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

document.querySelector('#normalizationForm').addEventListener('submit', async event => {
  event.preventDefault();
  const selected = document.querySelector('input[name=normalizedTerm]:checked');
  if (!selected || !pendingSearch) return;
  normalizationPanel.classList.add('hidden');
  await runSearch(selected.value, pendingSearch.datasets, pendingSearch.abbreviation);
});

document.querySelector('#cancelNormalization').addEventListener('click', () => {
  normalizationPanel.classList.add('hidden');
  pendingSearch = null;
});

async function runSearch(keyword, datasets, abbreviation = '') {
  searchButton.disabled = true;
  searchButton.querySelector('span').textContent = 'Searching…';
  try {
    const response = await fetch('/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword, datasets })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    lastSearch = { keyword, datasets };
    renderResults(data, abbreviation);
    if (data.unavailable.length) {
      message.textContent = `Upload ${data.unavailable.map(item => names[item]).join(', ')} to include it in this search.`;
    }
  } catch (error) {
    message.textContent = error.message;
  } finally {
    searchButton.disabled = false;
    searchButton.querySelector('span').textContent = 'Search records';
  }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' })[char]);
}

function renderResults(data, abbreviation = '') {
  const section = document.querySelector('#resultsSection');
  document.querySelector('#resultKeyword').textContent = data.expanded
    ? `${data.keyword} → ${data.search_terms.join('; ')}`
    : `“${data.keyword}”`;
  document.querySelector('#summary').innerHTML = data.summary.map(item => `
    <div class="summary-card"><strong>${item.matches.toLocaleString()}</strong><span>${names[item.dataset]}</span></div>`).join('');
  termSuggestion.classList.toggle('hidden', data.expanded);
  document.querySelector('#termSuggestionPrompt').classList.remove('hidden');
  termForm.classList.add('hidden');
  document.querySelector('#termFormMessage').textContent = '';
  document.querySelector('#resultTables').innerHTML = Object.entries(data.results).map(([kind, result]) => {
    const head = result.columns.map(column => `<th>${escapeHtml(column)}</th>`).join('');
    const body = result.rows.map(row => `<tr>${result.columns.map(column => `<td>${escapeHtml(row[column])}</td>`).join('')}</tr>`).join('');
    return `<article class="table-card">
      <header><h3 class="table-title">${names[kind]}</h3><span>${result.total.toLocaleString()} matches${result.truncated ? ' · first 500 shown' : ''}</span></header>
      ${result.total ? `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>` : '<p class="empty">No matching records found.</p>'}
    </article>`;
  }).join('');
  section.classList.remove('hidden');
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

document.querySelector('#openTermForm').addEventListener('click', () => {
  const keyword = lastSearch?.keyword || '';
  const looksLikeAbbreviation = !keyword.includes(' ') && keyword.length <= 12;
  document.querySelector('#termShort').value = looksLikeAbbreviation ? keyword : '';
  document.querySelector('#termLong').value = looksLikeAbbreviation ? '' : keyword;
  document.querySelector('#termAliases').value = '';
  document.querySelector('#termSuggestionPrompt').classList.add('hidden');
  termForm.classList.remove('hidden');
  (looksLikeAbbreviation ? document.querySelector('#termLong') : document.querySelector('#termShort')).focus();
});

document.querySelector('#cancelTermForm').addEventListener('click', () => {
  termForm.classList.add('hidden');
  document.querySelector('#termSuggestionPrompt').classList.remove('hidden');
});

termForm.addEventListener('submit', async event => {
  event.preventDefault();
  const submitButton = termForm.querySelector('button[type=submit]');
  const formMessage = document.querySelector('#termFormMessage');
  submitButton.disabled = true;
  formMessage.textContent = '';
  try {
    const response = await fetch('/medical-terms', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        short_term: document.querySelector('#termShort').value.trim(),
        long_term: document.querySelector('#termLong').value.trim(),
        search_terms: document.querySelector('#termAliases').value.trim()
      })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    termSuggestion.classList.add('hidden');
    message.textContent = 'Terminology saved. Re-running the search with all related terms.';
    await runSearch(lastSearch.keyword, lastSearch.datasets);
  } catch (error) {
    formMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

refreshStatus().catch(() => { message.textContent = 'Could not read dataset status.'; });
