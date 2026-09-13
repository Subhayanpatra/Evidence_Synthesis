"use strict";

const byId = (id) => document.getElementById(id);

const elements = {
    form: byId("search-form"),
    query: byId("medical-query"),
    paperCount: byId("paper-count"),
    useYearFilter: byId("use-year-filter"),
    yearFields: byId("year-fields"),
    startYear: byId("start-year"),
    endYear: byId("end-year"),
    runAgents: byId("run-agents"),
    maxAgentPapers: byId("max-agent-papers"),
    slrHandling: byId("slr-handling"),
    generateSap: byId("generate-sap"),
    searchButton: byId("search-button"),
    jobPanel: byId("job-panel"),
    jobStage: byId("job-stage"),
    jobPercent: byId("job-percent"),
    jobMessage: byId("job-message"),
    progressBar: byId("progress-bar"),
    progressTrack: document.querySelector(".progress-track"),
    normalizationBanner: byId("normalization-banner"),
    normalizedQuery: byId("normalized-query"),
    confidenceBadge: byId("confidence-badge"),
    resultsBody: byId("results-body"),
    resultSummary: byId("result-summary"),
    viewSheetButton: byId("view-sheet-button"),
    downloadButton: byId("download-button"),
    dataSheet: byId("data-sheet"),
    sheetTable: byId("sheet-table"),
    sheetColumnCount: byId("sheet-column-count"),
    closeSheetButton: byId("close-sheet-button"),
    sapResult: byId("sap-result"),
    sapSummary: byId("sap-summary"),
    sapContent: byId("sap-content"),
    downloadSapButton: byId("download-sap-button"),
    dialog: byId("paper-dialog"),
    dialogTitle: byId("dialog-title"),
    dialogPmcid: byId("dialog-pmcid"),
    dialogBody: byId("dialog-body"),
    dialogClose: byId("dialog-close"),
    cellDialog: byId("cell-dialog"),
    cellDialogTitle: byId("cell-dialog-title"),
    cellDialogPaper: byId("cell-dialog-paper"),
    cellDialogContent: byId("cell-dialog-content"),
    cellDialogClose: byId("cell-dialog-close"),
    queryDialog: byId("query-dialog"),
    queryConfirmationForm: byId("query-confirmation-form"),
    confirmedQuery: byId("confirmed-query"),
    ambiguityOptions: byId("ambiguity-options"),
    queryStyle: byId("query-style"),
    queryConfidence: byId("query-confidence"),
    queryDialogClose: byId("query-dialog-close"),
    cancelQueryButton: byId("cancel-query-button"),
    toast: byId("toast"),
    serviceDot: byId("service-dot"),
    serviceLabel: byId("service-label"),
    menuButton: byId("menu-button"),
    sidebar: byId("sidebar"),
    sidebarScrim: byId("sidebar-scrim"),
};

const metrics = {
    total: byId("metric-total"),
    pmc: byId("metric-pmc"),
    countries: byId("metric-countries"),
    codes: byId("metric-codes"),
};

let activeJobId = "";
let activePapers = [];
let toastTimer = null;
let pendingSearchPayload = null;

const preferredSheetColumns = [
    "PMCID",
    "PMID",
    "Title",
    "Journal",
    "PublicationYear",
    "Authors",
    "Affiliations",
    "Language",
    "DOI",
    "Status",
    "Abstract",
    "MeSH Terms",
    "Keywords",
    "Publication Types",
    "Chemical List",
    "PubMedURL",
    "PMCURL",
    "Relevant",
    "Relevance_Score",
    "Relevance_Reason",
    "Is_SLR",
    "Study_Design",
    "Is_SLR",
    "Study_Design",
    "ICD_9_CM",
    "ICD_10_CM",
    "ICD_10_PCS",
    "CPT",
    "HCPCS",
    "NDC",
    "Analysis",
    "Analyst result",
    "Query Supporting Evidence",
    "Outcome",
    "Country",
    "Supplementary_Status",
    "Supplementary_Files",
    "Supplementary_Content",
    "Full_Text",
    "Sections",
    "Figures",
    "Tables",
    "Agent_Error",
    "Code_Agent_Error",
    "Analysis_Agent_Error",
    "Query_Evidence_Agent_Error",
    "Outcome_Agent_Error",
];

function setServiceStatus(online) {
    elements.serviceDot.classList.toggle("online", online);
    elements.serviceDot.classList.toggle("offline", !online);
    elements.serviceLabel.textContent = online ? "Service online" : "Service unavailable";
}

async function checkHealth() {
    try {
        const response = await fetch("./api/health", { cache: "no-store" });
        setServiceStatus(response.ok);
    } catch {
        setServiceStatus(false);
    }
}

function toggleYearFields() {
    elements.yearFields.hidden = !elements.useYearFilter.checked;
}

function toggleAgentFields() {
    const enabled = elements.runAgents.checked;
    elements.maxAgentPapers.disabled = !enabled;
    elements.slrHandling.disabled = !enabled;
}

function setBusy(busy) {
    elements.searchButton.disabled = busy;
    elements.searchButton.querySelector("span").textContent = busy
        ? "Working…"
        : "Find evidence";
}

function showToast(message, type = "error") {
    window.clearTimeout(toastTimer);
    elements.toast.textContent = message;
    elements.toast.className = `toast ${type}`;
    elements.toast.hidden = false;
    toastTimer = window.setTimeout(() => {
        elements.toast.hidden = true;
    }, 6500);
}

function errorMessage(payload, fallback) {
    const detail = payload?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
        return detail.map((item) => item.msg || "Invalid value").join(" ");
    }
    return fallback;
}

async function fetchJson(url, options = {}) {
    const response = await fetch(url, options);
    let payload = {};
    try {
        payload = await response.json();
    } catch {
        payload = {};
    }
    if (!response.ok) {
        throw new Error(errorMessage(payload, `Request failed (${response.status}).`));
    }
    return payload;
}

function buildSearchPayload() {
    const paperCount = Number(elements.paperCount.value);
    const runAgents = elements.runAgents.checked;
    const maxAgentPapers = runAgents
        ? Number(elements.maxAgentPapers.value)
        : 5;
    const startYear = Number(elements.startYear.value);
    const endYear = Number(elements.endYear.value);

    if (!Number.isInteger(paperCount) || paperCount < 1 || paperCount > 200) {
        throw new Error("PMC papers must be between 1 and 200.");
    }
    if (
        runAgents
        && (!Number.isInteger(maxAgentPapers)
            || maxAgentPapers < 1
            || maxAgentPapers > 200)
    ) {
        throw new Error("Papers to analyze must be between 1 and 200.");
    }
    if (elements.useYearFilter.checked && startYear > endYear) {
        throw new Error("Start year must be less than or equal to end year.");
    }

    return {
        medical_query: elements.query.value.trim(),
        paper_count: paperCount,
        use_year_filter: elements.useYearFilter.checked,
        start_year: elements.useYearFilter.checked ? startYear : null,
        end_year: elements.useYearFilter.checked ? endYear : null,
        run_agents: runAgents,
        max_agent_papers: maxAgentPapers,
        slr_handling: elements.slrHandling.value,
        generate_sap: elements.generateSap.checked,
    };
}

async function startConfirmedSearch(payload) {
    resetResults();
    const created = await fetchJson("./api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
    });
    activeJobId = created.job_id;
    await pollJob(activeJobId);
}

function resetResults() {
    activePapers = [];
    elements.downloadButton.hidden = true;
    elements.viewSheetButton.hidden = true;
    elements.dataSheet.hidden = true;
    elements.sapResult.hidden = true;
    elements.sapContent.replaceChildren();
    elements.sheetTable.replaceChildren();
    elements.normalizationBanner.hidden = true;
    elements.resultSummary.textContent = "Your search is running.";
    metrics.total.textContent = "0";
    metrics.pmc.textContent = "0";
    metrics.countries.textContent = "0";
    metrics.codes.textContent = "0";
    elements.resultsBody.replaceChildren(createEmptyRow(
        "Searching medical, clinical, healthcare, and life-sciences research literature…",
        "Results will appear here when processing is complete.",
        "fa-spinner"
    ));
}

function updateJob(job) {
    const progress = Math.max(0, Math.min(100, Number(job.progress) || 0));
    const stage = String(job.stage || "processing").replaceAll("_", " ");
    elements.jobPanel.hidden = false;
    elements.jobStage.textContent = stage.charAt(0).toUpperCase() + stage.slice(1);
    elements.jobPercent.textContent = `${progress}%`;
    elements.jobMessage.textContent = job.message || "Processing…";
    elements.progressBar.style.width = `${progress}%`;
    elements.progressTrack.setAttribute("aria-valuenow", String(progress));
}

async function pollJob(jobId) {
    while (activeJobId === jobId) {
        const job = await fetchJson(`./api/jobs/${encodeURIComponent(jobId)}`, {
            cache: "no-store",
        });
        updateJob(job);

        if (job.status === "complete") {
            renderResult(job.result, jobId);
            setBusy(false);
            return;
        }
        if (job.status === "failed") {
            throw new Error(job.error || "The search could not be completed.");
        }
        await new Promise((resolve) => window.setTimeout(resolve, 1000));
    }
}

async function submitSearch(event) {
    event.preventDefault();
    try {
        const payload = buildSearchPayload();
        if (!payload.medical_query) {
            throw new Error("Enter a medical research query.");
        }

        setBusy(true);
        const normalization = await fetchJson("./api/normalize", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ medical_query: payload.medical_query }),
        });
        pendingSearchPayload = {
            ...payload,
            normalization_confidence: Number(normalization.confidence) || 0,
            normalization_query_style:
                normalization.query_style === "detailed_query"
                    ? "detailed_query"
                    : "keyword_query",
        };
        const options = Array.isArray(normalization.ambiguity_options)
            ? normalization.ambiguity_options
            : [];
        elements.ambiguityOptions.replaceChildren();
        elements.ambiguityOptions.hidden = !normalization.requires_user_selection;
        if (normalization.requires_user_selection) {
            options.forEach((option) => {
                const item = document.createElement("option");
                item.value = option.normalized_query;
                item.textContent = option.category
                    ? `${option.full_form} — ${option.category}`
                    : option.full_form;
                elements.ambiguityOptions.append(item);
            });
            const none = document.createElement("option");
            none.value = "";
            none.textContent = "None of the above";
            elements.ambiguityOptions.append(none);
        }
        elements.confirmedQuery.value =
            normalization.normalized_query || options[0]?.normalized_query || "";
        elements.queryStyle.textContent = String(
            normalization.query_style || "normalized query"
        ).replaceAll("_", " ");
        elements.queryConfidence.textContent =
            `${Math.round((Number(normalization.confidence) || 0) * 100)}% confidence`;
        elements.queryDialog.showModal();
        setBusy(false);
    } catch (error) {
        setBusy(false);
        elements.jobPanel.hidden = true;
        elements.resultSummary.textContent = "Search failed. Review the message and try again.";
        elements.resultsBody.replaceChildren(createEmptyRow(
            "The search could not be completed.",
            error.message,
            "fa-triangle-exclamation"
        ));
        showToast(error.message);
    }
}

async function confirmNormalizedQuery(event) {
    event.preventDefault();
    const normalizedQuery = elements.confirmedQuery.value.trim();
    if (!pendingSearchPayload || !normalizedQuery) {
        showToast("Enter or select a normalized query before searching.");
        return;
    }

    const payload = {
        ...pendingSearchPayload,
        normalized_query: normalizedQuery,
        query_confirmed: true,
    };
    elements.queryDialog.close();
    pendingSearchPayload = null;
    setBusy(true);
    try {
        await startConfirmedSearch(payload);
    } catch (error) {
        setBusy(false);
        elements.jobPanel.hidden = true;
        showToast(error.message);
    }
}

function cancelNormalizedQuery() {
    pendingSearchPayload = null;
    elements.queryDialog.close();
    setBusy(false);
    showToast("Search cancelled. Europe PMC was not searched.", "success");
}

function createEmptyRow(title, message, icon) {
    const row = document.createElement("tr");
    row.className = "empty-row";
    const cell = document.createElement("td");
    cell.colSpan = 5;
    const state = document.createElement("div");
    state.className = "empty-state";
    const iconElement = document.createElement("i");
    iconElement.className = `fa-solid ${icon}`;
    iconElement.setAttribute("aria-hidden", "true");
    const strong = document.createElement("strong");
    strong.textContent = title;
    const span = document.createElement("span");
    span.textContent = message;
    state.append(iconElement, strong, span);
    cell.append(state);
    row.append(cell);
    return row;
}

function textCell(value) {
    const cell = document.createElement("td");
    cell.textContent = value || "—";
    return cell;
}

function aiStatus(paper) {
    if (paper.Agent_Error) return { label: "Error", className: "error", icon: "fa-circle-exclamation" };
    if (paper.Relevant === true) return { label: "Relevant", className: "relevant", icon: "fa-circle-check" };
    if (paper.Relevant === false) return { label: "Not relevant", className: "not-relevant", icon: "fa-circle-xmark" };
    return { label: "Not analyzed", className: "pending", icon: "fa-minus" };
}

function paperRow(paper, index) {
    const row = document.createElement("tr");

    const paperCell = document.createElement("td");
    paperCell.className = "paper-cell";
    const title = document.createElement("strong");
    title.textContent = paper.Title || "Untitled paper";
    const id = document.createElement("span");
    id.textContent = paper.PMCID || paper.PMID || "No identifier";
    paperCell.append(title, id);

    row.append(
        paperCell,
        textCell(paper.PublicationYear),
        textCell(paper.Country),
    );

    const statusCell = document.createElement("td");
    const status = aiStatus(paper);
    const badge = document.createElement("span");
    badge.className = `badge ${status.className}`;
    const statusIcon = document.createElement("i");
    statusIcon.className = `fa-solid ${status.icon}`;
    statusIcon.setAttribute("aria-hidden", "true");
    badge.append(statusIcon, document.createTextNode(status.label));
    statusCell.append(badge);
    row.append(statusCell);

    const actionCell = document.createElement("td");
    const button = document.createElement("button");
    button.type = "button";
    button.className = "view-button";
    button.dataset.paperIndex = String(index);
    button.append(
        document.createTextNode("View "),
        Object.assign(document.createElement("i"), {
            className: "fa-solid fa-arrow-right",
        })
    );
    actionCell.append(button);
    row.append(actionCell);

    return row;
}

function renderResult(result, jobId) {
    const normalization = result.normalization || {};
    const resultMetrics = result.metrics || {};
    activePapers = Array.isArray(result.papers) ? result.papers : [];

    elements.normalizedQuery.textContent = normalization.normalized_query || "";
    elements.confidenceBadge.textContent =
        `${Math.round((Number(normalization.confidence) || 0) * 100)}% confidence`;
    elements.normalizationBanner.hidden = false;

    metrics.total.textContent = String(resultMetrics.total_papers || 0);
    metrics.pmc.textContent = String(resultMetrics.pmc_articles || 0);
    metrics.countries.textContent = String(resultMetrics.countries || 0);
    metrics.codes.textContent = String(resultMetrics.medical_codes || 0);

    elements.resultSummary.textContent =
        `Found ${result.returned} of ${result.requested} requested relevant PMC papers ` +
        `after assessing ${result.candidates_assessed || 0} candidates ` +
        `(${result.not_relevant || 0} not relevant, ${result.excluded_slr || 0} SLR excluded).`;
    elements.resultsBody.replaceChildren(
        ...(activePapers.length
            ? activePapers.map(paperRow)
            : [createEmptyRow("No PMC papers found.", "Try a broader medical query or date range.", "fa-folder-open")])
    );
    elements.downloadButton.href = `./api/jobs/${encodeURIComponent(jobId)}/download`;
    elements.downloadButton.hidden = activePapers.length === 0;
    elements.viewSheetButton.hidden = activePapers.length === 0;
    renderDataSheet();
    renderSap(result.sap, result.sap_requested, jobId);
    elements.jobPanel.hidden = true;
    document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderSap(sap, requested, jobId) {
    elements.sapContent.replaceChildren();
    if (!requested) {
        elements.sapResult.hidden = true;
        return;
    }

    elements.sapResult.hidden = false;
    elements.downloadSapButton.href = `./api/jobs/${encodeURIComponent(jobId)}/sap/download`;
    const contributing = Number(sap?.["Contributing extracted papers"] || 0);
    const returned = Number(sap?.["Returned relevant papers"] || 0);
    const requestedCount = Number(sap?.["Requested papers"] || 0);
    elements.sapSummary.textContent =
        `${requestedCount} papers requested; ${returned} relevant papers returned; ` +
        `${contributing} extracted papers contributed to this single draft SAP.`;

    if (!sap || sap.SAP_Agent_Error) {
        const block = document.createElement("article");
        block.className = "sap-block";
        const heading = document.createElement("h3");
        heading.textContent = "SAP generation status";
        const message = document.createElement("p");
        message.textContent = sap?.SAP_Agent_Error || "SAP generation did not return content.";
        block.append(heading, message);
        elements.sapContent.append(block);
        return;
    }

    Object.entries(sap).forEach(([label, value]) => {
        if (["Requested papers", "Returned relevant papers", "Contributing extracted papers"].includes(label)) return;
        if (value === null || value === "" || (Array.isArray(value) && value.length === 0)) return;
        const block = document.createElement("article");
        block.className = "sap-block";
        const heading = document.createElement("h3");
        heading.textContent = label;
        block.append(heading);
        if (Array.isArray(value)) {
            const list = document.createElement("ul");
            value.forEach((item) => {
                const entry = document.createElement("li");
                entry.textContent = String(item);
                list.append(entry);
            });
            block.append(list);
        } else {
            const text = document.createElement("p");
            text.textContent = String(value);
            block.append(text);
        }
        elements.sapContent.append(block);
    });
}

function stringify(value) {
    if (value === null || value === undefined || value === "") return "";
    if (typeof value === "string") return value;
    return JSON.stringify(value, null, 2);
}

function sheetColumns() {
    const discovered = new Set();
    activePapers.forEach((paper) => {
        Object.keys(paper).forEach((key) => discovered.add(key));
    });
    const ordered = preferredSheetColumns.filter((column) => discovered.delete(column));
    return [...ordered, ...Array.from(discovered).sort((a, b) => a.localeCompare(b))];
}

function sheetCell(value, rowIndex, column) {
    const cell = document.createElement("td");
    const text = stringify(value);
    if (!text) {
        cell.textContent = "—";
        cell.className = "sheet-empty";
        return cell;
    }

    const preview = document.createElement("span");
    preview.className = "sheet-cell-preview";
    preview.textContent = text.length > 240 ? `${text.slice(0, 240)}…` : text;

    if (text.length > 160 || text.includes("\n")) {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "sheet-cell-button";
        button.dataset.sheetRow = String(rowIndex);
        button.dataset.sheetColumn = column;
        button.title = `View complete ${column} value`;
        button.append(preview);
        cell.append(button);
    } else {
        cell.append(preview);
    }
    return cell;
}

function renderDataSheet() {
    elements.sheetTable.replaceChildren();
    if (!activePapers.length) return;

    const columns = sheetColumns();
    elements.sheetColumnCount.textContent =
        `${activePapers.length} rows × ${columns.length} columns.`;

    const head = document.createElement("thead");
    const headerRow = document.createElement("tr");
    const numberHeader = document.createElement("th");
    numberHeader.className = "sheet-row-number";
    numberHeader.scope = "col";
    numberHeader.textContent = "#";
    headerRow.append(numberHeader);
    columns.forEach((column) => {
        const header = document.createElement("th");
        header.scope = "col";
        header.textContent = column;
        header.title = column;
        headerRow.append(header);
    });
    head.append(headerRow);

    const body = document.createElement("tbody");
    activePapers.forEach((paper, rowIndex) => {
        const row = document.createElement("tr");
        const rowNumber = document.createElement("th");
        rowNumber.className = "sheet-row-number";
        rowNumber.scope = "row";
        rowNumber.textContent = String(rowIndex + 1);
        row.append(rowNumber);
        columns.forEach((column) => {
            row.append(sheetCell(paper[column], rowIndex, column));
        });
        body.append(row);
    });

    elements.sheetTable.append(head, body);
}

function setSheetVisible(visible) {
    elements.dataSheet.hidden = !visible;
    const buttonLabel = elements.viewSheetButton.querySelector("span");
    buttonLabel.textContent = visible ? "Hide Excel table" : "View Excel table";
    if (visible) {
        elements.dataSheet.scrollIntoView({ behavior: "smooth", block: "start" });
    }
}

function openSheetCell(rowIndex, column) {
    const paper = activePapers[rowIndex];
    if (!paper) return;
    elements.cellDialogPaper.textContent =
        `${paper.PMCID || paper.PMID || `Row ${rowIndex + 1}`} · ${column}`;
    elements.cellDialogTitle.textContent = column;
    elements.cellDialogContent.textContent = stringify(paper[column]) || "Not available";
    elements.cellDialog.showModal();
}

function detailItem(label, value) {
    const item = document.createElement("div");
    item.className = "detail-item";
    const labelElement = document.createElement("span");
    labelElement.textContent = label;
    const valueElement = document.createElement("strong");
    valueElement.textContent = stringify(value) || "Not available";
    item.append(labelElement, valueElement);
    return item;
}

function detailSection(title, value, collapsible = false) {
    const text = stringify(value);
    if (!text) return null;
    const section = document.createElement("section");
    section.className = "detail-section";
    const heading = document.createElement("h3");
    heading.textContent = title;
    section.append(heading);

    if (collapsible) {
        const details = document.createElement("details");
        const summary = document.createElement("summary");
        summary.textContent = `Show ${title.toLowerCase()}`;
        const content = document.createElement("pre");
        content.textContent = text;
        details.append(summary, content);
        section.append(details);
    } else {
        const content = document.createElement("p");
        content.textContent = text;
        section.append(content);
    }
    return section;
}

function linkSection(paper) {
    const links = [
        ["PubMed", paper.PubMedURL],
        ["PMC full article", paper.PMCURL],
        ["DOI", paper.DOI ? `https://doi.org/${paper.DOI}` : ""],
    ].filter(([, url]) => /^https:\/\//i.test(url || ""));
    if (!links.length) return null;

    const section = document.createElement("section");
    section.className = "detail-section";
    const heading = document.createElement("h3");
    heading.textContent = "Article links";
    section.append(heading);
    links.forEach(([label, url], index) => {
        const link = document.createElement("a");
        link.href = url;
        link.target = "_blank";
        link.rel = "noopener noreferrer";
        link.textContent = label;
        section.append(link);
        if (index < links.length - 1) section.append(document.createTextNode(" · "));
    });
    return section;
}

function openPaper(index) {
    const paper = activePapers[index];
    if (!paper) return;

    elements.dialogPmcid.textContent = paper.PMCID || paper.PMID || "Paper details";
    elements.dialogTitle.textContent = paper.Title || "Untitled paper";
    elements.dialogBody.replaceChildren();

    const grid = document.createElement("div");
    grid.className = "detail-grid";
    grid.append(
        detailItem("Journal", paper.Journal),
        detailItem("Published", paper.PublicationYear),
        detailItem("Country", paper.Country),
        detailItem("Authors", paper.Authors),
        detailItem("Language", paper.Language),
        detailItem("Relevance", paper.Relevant === undefined ? "Not analyzed" : String(paper.Relevant)),
    );
    elements.dialogBody.append(grid);

    const sections = [
        linkSection(paper),
        detailSection("Outcome", paper.Outcome),
        detailSection("Relevance reason", paper.Relevance_Reason),
        detailSection("Analysis methods", paper.Analysis),
        detailSection("Analysis results", paper["Analyst result"]),
        detailSection("Query supporting evidence", paper["Query Supporting Evidence"]),
        detailSection(
            "Medical codes",
            {
                ICD_9_CM: paper.ICD_9_CM || "",
                ICD_10_CM: paper.ICD_10_CM || "",
                ICD_10_PCS: paper.ICD_10_PCS || "",
                CPT: paper.CPT || "",
                HCPCS: paper.HCPCS || "",
                NDC: paper.NDC || "",
            }
        ),
        detailSection("Abstract", paper.Abstract),
        detailSection("Affiliations", paper.Affiliations),
        detailSection("MeSH terms", paper["MeSH Terms"]),
        detailSection("Keywords", paper.Keywords),
        detailSection("Supplementary status", paper.Supplementary_Status),
        detailSection("Supplementary files", paper.Supplementary_Files, true),
        detailSection("Full text", paper.Full_Text, true),
        detailSection("Sections", paper.Sections, true),
        detailSection("Tables", paper.Tables, true),
        detailSection("Figures", paper.Figures, true),
        detailSection("Supplementary content", paper.Supplementary_Content, true),
        detailSection("Processing error", paper.Agent_Error || paper.Code_Agent_Error || paper.Analysis_Agent_Error || paper.Query_Evidence_Agent_Error || paper.Outcome_Agent_Error),
    ].filter(Boolean);
    elements.dialogBody.append(...sections);
    elements.dialog.showModal();
}

function toggleSidebar(open) {
    elements.sidebar.classList.toggle("open", open);
    elements.sidebarScrim.hidden = !open;
    elements.menuButton.setAttribute("aria-expanded", String(open));
}

elements.form.addEventListener("submit", submitSearch);
elements.queryConfirmationForm.addEventListener("submit", confirmNormalizedQuery);
elements.queryDialogClose.addEventListener("click", cancelNormalizedQuery);
elements.cancelQueryButton.addEventListener("click", cancelNormalizedQuery);
elements.ambiguityOptions.addEventListener("change", () => {
    elements.confirmedQuery.value = elements.ambiguityOptions.value;
});
elements.useYearFilter.addEventListener("change", toggleYearFields);
elements.runAgents.addEventListener("change", toggleAgentFields);
elements.resultsBody.addEventListener("click", (event) => {
    const button = event.target.closest("[data-paper-index]");
    if (button) openPaper(Number(button.dataset.paperIndex));
});
elements.dialogClose.addEventListener("click", () => elements.dialog.close());
elements.dialog.addEventListener("click", (event) => {
    if (event.target === elements.dialog) elements.dialog.close();
});
elements.viewSheetButton.addEventListener("click", () => {
    setSheetVisible(elements.dataSheet.hidden);
});
elements.closeSheetButton.addEventListener("click", () => setSheetVisible(false));
elements.sheetTable.addEventListener("click", (event) => {
    const button = event.target.closest("[data-sheet-row]");
    if (button) {
        openSheetCell(Number(button.dataset.sheetRow), button.dataset.sheetColumn);
    }
});
elements.cellDialogClose.addEventListener("click", () => elements.cellDialog.close());
elements.cellDialog.addEventListener("click", (event) => {
    if (event.target === elements.cellDialog) elements.cellDialog.close();
});
elements.menuButton.addEventListener("click", () => {
    toggleSidebar(!elements.sidebar.classList.contains("open"));
});
elements.sidebarScrim.addEventListener("click", () => toggleSidebar(false));

document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".nav-item").forEach((item) => item.classList.remove("active"));
        button.classList.add("active");
        const target = byId(button.dataset.target);
        if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
        toggleSidebar(false);
    });
});

toggleYearFields();
toggleAgentFields();
checkHealth();
