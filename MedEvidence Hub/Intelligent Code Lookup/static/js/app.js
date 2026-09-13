const names = { diagnosis: 'Diagnosis codes', procedure: 'Procedure codes', ndc: 'NDC codes' };
const setupPanel = document.querySelector('#setupPanel');
const message = document.querySelector('#message');
const searchButton = document.querySelector('#searchForm .search-submit');
const normalizationPanel = document.querySelector('#normalizationPanel');
const termSuggestion = document.querySelector('#termSuggestion');
const termForm = document.querySelector('#termForm');
const recordEditor = document.querySelector('#recordEditor');
const datasetMessage = document.querySelector('#datasetMessage');
let pendingSearch = null;
let lastSearch = null;
let activeRecordKind = null;

document.querySelector('#setupToggle').addEventListener('click', () => setupPanel.classList.toggle('hidden'));
document.querySelector('#closeSetup').addEventListener('click', () => setupPanel.classList.add('hidden'));
document.querySelector('#clearSearch').addEventListener('click', () => {
  document.querySelector('#keyword').value = '';
  document.querySelector('#keyword').focus();
});

async function refreshStatus() {
  const response = await fetch('./status');
  const status = await response.json();
  const cards = document.querySelector('#datasetCards');
  cards.innerHTML = Object.entries(status).map(([kind, data]) => `
    <article class="dataset-card ${data.loaded ? 'loaded' : ''}">
      <h3>${names[kind]}</h3>
      <p>${data.base_loaded ? `${data.base_rows.toLocaleString()} parent records` : (data.error || `Parent file ${data.filename} is unavailable`)}</p>
      <small>${data.user_rows.toLocaleString()} user-added records</small>
      <div class="dataset-actions">
        <button class="upload-label add-record-button" type="button" data-kind="${kind}">Add one record</button>
        <button class="upload-label import-record-button" type="button" data-kind="${kind}">Import CSV</button>
        <input class="record-file-input" type="file" accept=".csv,text/csv" data-kind="${kind}" hidden>
      </div>
    </article>`).join('');

  cards.querySelectorAll('.add-record-button').forEach(button => button.addEventListener('click', openRecordEditor));
  cards.querySelectorAll('.import-record-button').forEach(button => button.addEventListener('click', event => {
    event.currentTarget.parentElement.querySelector('.record-file-input').click();
  }));
  cards.querySelectorAll('.record-file-input').forEach(input => input.addEventListener('change', importRecords));
  if (Object.values(status).some(data => !data.base_loaded)) setupPanel.classList.remove('hidden');
}

async function importRecords(event) {
  const input = event.currentTarget;
  if (!input.files.length) return;
  const kind = input.dataset.kind;
  const button = input.parentElement.querySelector('.import-record-button');
  const originalLabel = button.textContent;
  const formData = new FormData();
  formData.append('kind', kind);
  formData.append('file', input.files[0]);
  button.disabled = true;
  button.textContent = 'Importing...';
  datasetMessage.textContent = '';
  try {
    const response = await fetch('./records/import', { method: 'POST', body: formData });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    datasetMessage.textContent = result.message;
    await refreshStatus();
  } catch (error) {
    datasetMessage.textContent = error.message;
    button.disabled = false;
    button.textContent = originalLabel;
  } finally {
    input.value = '';
  }
}

function openRecordEditor(event) {
  activeRecordKind = event.currentTarget.dataset.kind;
  const isNdc = activeRecordKind === 'ndc';
  document.querySelector('#record-editor-title').textContent = `Add ${names[activeRecordKind].replace(' codes', '')} record`;
  document.querySelector('#recordEditorHelp').textContent = `Saved in uploads/${activeRecordKind}/user_records.csv. The parent CSV will not be changed.`;
  document.querySelector('#recordFields').innerHTML = isNdc ? `
    <label>NDC code<input name="ndc" type="text" maxlength="500" placeholder="e.g. 250" required></label>
    <label>Pharm classes<input name="pharm_classes" type="text" maxlength="500"></label>
    <label>Proprietary name<input name="proprietary_name" type="text" maxlength="500" placeholder="Brand name"></label>
    <label>Nonproprietary name<input name="nonproprietary_name" type="text" maxlength="500" placeholder="Generic name"></label>
    <label>Substance name<input name="substance_name" type="text" maxlength="500" placeholder="Active ingredient"></label>
    <label>GENERID<input name="generid" type="text" maxlength="500"></label>
    <label>GENIND<input name="genind" type="text" maxlength="500"></label>
    <label>Dosage form name<input name="dosage_form_name" type="text" maxlength="500"></label>
    <label>Active numerator strength<input name="active_numerator_strength" type="text" maxlength="500"></label>
    <label>Strength (STRNGTH)<input name="strength" type="text" maxlength="500"></label>
    <label>Active ingredient unit<input name="active_ingredient_unit" type="text" maxlength="500"></label>
    <label>USC<input name="usc" type="text" maxlength="500"></label>
    <label>USC description<input name="usc_desc" type="text" maxlength="500"></label>
  ` : `
    <label>Code type<input name="code_type" type="text" maxlength="500" placeholder="e.g. ${activeRecordKind === 'diagnosis' ? 'DIAG' : 'PROC'}"></label>
    <label>Code version<input name="code_version" type="text" maxlength="500" placeholder="e.g. ICD-10-CM"></label>
    <label>Code<input name="code" type="text" maxlength="500" placeholder="e.g. I639" required></label>
    <label>Description<input name="description" type="text" maxlength="500" placeholder="Medical code description" required></label>
    <label>Bill type<input name="bill_type" type="text" maxlength="500"></label>
    <label>Cancer type<input name="cancer_type" type="text" maxlength="500"></label>
    <label>Cancer<input name="cancer" type="text" maxlength="500"></label>
    <label>NET<input name="net" type="text" maxlength="500"></label>
    <label>Newly identified<input name="newly_identified" type="text" maxlength="500"></label>
  `;
  document.querySelector('#recordMessage').textContent = '';
  recordEditor.classList.remove('hidden');
  recordEditor.querySelector('input').focus();
  recordEditor.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function closeRecordEditor() {
  recordEditor.classList.add('hidden');
  activeRecordKind = null;
}

document.querySelector('#closeRecordEditor').addEventListener('click', closeRecordEditor);
document.querySelector('#cancelRecord').addEventListener('click', closeRecordEditor);

document.querySelector('#recordForm').addEventListener('submit', async event => {
  event.preventDefault();
  if (!activeRecordKind) return;
  const submitButton = event.currentTarget.querySelector('button[type=submit]');
  const recordMessage = document.querySelector('#recordMessage');
  const payload = { kind: activeRecordKind };
  new FormData(event.currentTarget).forEach((value, key) => { payload[key] = String(value).trim(); });
  submitButton.disabled = true;
  recordMessage.textContent = '';
  try {
    const response = await fetch('./records', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error);
    closeRecordEditor();
    message.textContent = result.message;
    await refreshStatus();
  } catch (error) {
    recordMessage.textContent = error.message;
  } finally {
    submitButton.disabled = false;
  }
});

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
  searchButton.textContent = 'Searching...';
  try {
    const response = await fetch('./search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ keyword, datasets })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error);
    lastSearch = { keyword, datasets };
    renderResults(data, abbreviation);
    if (data.unavailable.length) {
      message.textContent = `Ask an administrator to provide ${data.unavailable.map(item => names[item]).join(', ')}.`;
    }
  } catch (error) {
    message.textContent = error.message;
  } finally {
    searchButton.disabled = false;
    searchButton.textContent = 'Search';
  }
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>'"]/g, char => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', "'":'&#39;', '"':'&quot;' })[char]);
}

function renderResults(data, abbreviation = '') {
  const section = document.querySelector('#resultsSection');
  document.querySelector('#resultKeyword').textContent = data.expanded
    ? `${data.keyword} -> ${data.search_terms.join('; ')}`
    : `"${data.keyword}"`;
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
      <header><h3 class="table-title">${names[kind]}</h3><span>${result.total.toLocaleString()} matches${result.truncated ? ' - first 500 shown' : ''}</span></header>
      ${result.total ? `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>` : '<p class="empty">No matching records found.</p>'}
    </article>`;
  }).join('');
  renderRepositorySummary(data);
  section.classList.remove('hidden');
  section.scrollIntoView({ behavior: 'smooth', block: 'start' });
}

function renderRepositorySummary(data) {
  const labels = { diagnosis: 'Diagnosis codes', procedure: 'Procedure codes', ndc: 'NDC codes' };
  const codeColumn = row => Object.keys(row).find(key => ['code', 'codes', 'ndc'].includes(key.toLowerCase()));
  const summary = Object.entries(data.results).map(([kind, result]) => {
    const rows = result.rows.slice(0, 5);
    const links = rows.length ? rows.map(row => {
      const key = codeColumn(row);
      const value = key ? row[key] : 'Record';
      return `<a href="#resultTables">${escapeHtml(value)} <span>↗</span></a>`;
    }).join('') : '<p>No matching records found.</p>';
    return `<section class="repository-group"><h3>${labels[kind]} <span>${result.total.toLocaleString()}</span></h3>${links}</section>`;
  }).join('');
  document.querySelector('#repositorySummary').innerHTML = summary || '<p>No local results available.</p>';

  // This panel intentionally remains a front-end placeholder until the
  // intelligence service is connected. It must not present local matches as AI suggestions.
  ['smartDiagnosis', 'smartProcedure', 'smartNdc', 'smartTotal'].forEach(id => {
    document.querySelector(`#${id}`).textContent = '—';
  });
  document.querySelector('#intelligenceNote').textContent = 'Local results are shown below. Connect your intelligence backend to show additional suggested codes.';
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
    const response = await fetch('./medical-terms', {
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
