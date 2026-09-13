from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "AI_Extract_Complete_Beginner_User_Manual.docx"
BLUE = "2E74B5"
DARK = "1F4D78"
LIGHT = "E8EEF5"
PALE = "F4F6F9"
GREEN = "0B7A61"
RED = "9B1C1C"


def font(run, size=11, bold=False, color="000000", italic=False):
    run.font.name = "Calibri"
    run._element.get_or_add_rPr().rFonts.set(qn("w:ascii"), "Calibri")
    run._element.get_or_add_rPr().rFonts.set(qn("w:hAnsi"), "Calibri")
    run.font.size = Pt(size)
    run.bold = bold
    run.italic = italic
    run.font.color.rgb = RGBColor.from_string(color)


def shade(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def margins(cell, top=80, start=120, bottom=80, end=120):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_width(cell, dxa):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(dxa))
    tc_w.set(qn("w:type"), "dxa")


def table_geometry(table, widths):
    total = sum(widths)
    table.autofit = False
    table.alignment = WD_TABLE_ALIGNMENT.LEFT
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(total))
    tbl_w.set(qn("w:type"), "dxa")
    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")
    grid = table._tbl.tblGrid
    for child in list(grid):
        grid.remove(child)
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    for row in table.rows:
        for i, cell in enumerate(row.cells):
            set_cell_width(cell, widths[i])
            margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def add_table(doc, headers, rows, widths):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table_geometry(table, widths)
    tr_pr = table.rows[0]._tr.get_or_add_trPr()
    tbl_header = OxmlElement("w:tblHeader")
    tbl_header.set(qn("w:val"), "true")
    tr_pr.append(tbl_header)
    for i, text in enumerate(headers):
        shade(table.rows[0].cells[i], LIGHT)
        p = table.rows[0].cells[i].paragraphs[0]
        p.paragraph_format.space_after = Pt(0)
        font(p.add_run(text), 10, True, DARK)
    for row_data in rows:
        row = table.add_row()
        for i, value in enumerate(row_data):
            p = row.cells[i].paragraphs[0]
            p.paragraph_format.space_after = Pt(0)
            font(p.add_run(str(value)), 9.5)
    table_geometry(table, widths)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)
    return table


def add_callout(doc, label, text, color=BLUE):
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    table_geometry(table, [9360])
    shade(table.cell(0, 0), PALE)
    p = table.cell(0, 0).paragraphs[0]
    p.paragraph_format.space_after = Pt(0)
    font(p.add_run(f"{label}: "), 10.5, True, color)
    font(p.add_run(text), 10.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(0)


def para(doc, text="", bold_lead=None):
    p = doc.add_paragraph()
    if bold_lead and text.startswith(bold_lead):
        font(p.add_run(bold_lead), 11, True, DARK)
        font(p.add_run(text[len(bold_lead):]), 11)
    else:
        font(p.add_run(text), 11)
    return p


def bullet(doc, text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.25
    font(p.add_run(text), 11)


def step(doc, title, text):
    p = doc.add_paragraph(style="List Number")
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.line_spacing = 1.25
    font(p.add_run(f"{title}. "), 11, True, DARK)
    font(p.add_run(text), 11)


def page_break(doc):
    doc.add_page_break()


doc = Document()
section = doc.sections[0]
section.page_width = Inches(8.5)
section.page_height = Inches(11)
section.top_margin = section.bottom_margin = Inches(1)
section.left_margin = section.right_margin = Inches(1)
section.header_distance = section.footer_distance = Inches(0.492)

styles = doc.styles
normal = styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)
normal.paragraph_format.space_after = Pt(6)
normal.paragraph_format.line_spacing = 1.25
for name, size, color, before, after in (
    ("Heading 1", 16, BLUE, 18, 10),
    ("Heading 2", 13, BLUE, 14, 7),
    ("Heading 3", 12, DARK, 10, 5),
):
    style = styles[name]
    style.font.name = "Calibri"
    style.font.size = Pt(size)
    style.font.bold = True
    style.font.color.rgb = RGBColor.from_string(color)
    style.paragraph_format.space_before = Pt(before)
    style.paragraph_format.space_after = Pt(after)
    style.paragraph_format.keep_with_next = True
for name in ("List Bullet", "List Number"):
    styles[name].font.name = "Calibri"
    styles[name].font.size = Pt(11)
    styles[name].paragraph_format.left_indent = Inches(0.375)
    styles[name].paragraph_format.first_line_indent = Inches(-0.188)
    styles[name].paragraph_format.space_after = Pt(4)
    styles[name].paragraph_format.line_spacing = 1.25

header = section.header.paragraphs[0]
header.alignment = WD_ALIGN_PARAGRAPH.RIGHT
font(header.add_run("AI EXTRACT  |  USER MANUAL"), 8.5, True, DARK)
footer = section.footer.paragraphs[0]
footer.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(footer.add_run("Local biomedical evidence extraction platform  |  Beginner edition"), 8.5, False, "666666")

# Cover
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(105)
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("AI EXTRACT"), 30, True, DARK)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("Complete User Manual & Project Documentation"), 17, True, BLUE)
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("Search PubMed/PMC, retrieve full text and supplementary files,\nand extract structured medical, clinical, healthcare, and life-sciences research evidence with OpenAI GPT"), 12, False, "555555")
p.paragraph_format.space_after = Pt(32)
add_callout(doc, "Who this is for", "A person receiving this project from GitHub for the first time, including someone who has never used PyCharm, Python virtual environments, APIs, or website development.")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
p.paragraph_format.space_before = Pt(55)
font(p.add_run("Prepared from the AI_extract project source code"), 10, False, "666666")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("Documentation date: 10 August 2026"), 10, True, DARK)

page_break(doc)
doc.add_heading("How to use this manual", level=1)
para(doc, "Start with Part A if you only need to use the website. Use Part B if you need to install or start it. Use Part C for administration, troubleshooting, or development.")
add_table(doc, ["Reader", "Best starting point"], [
    ("First-time website user", "Quick start, then Running a search"),
    ("Researcher / analyst", "AI extraction, results, paper details, CSV export"),
    ("Project owner / administrator", "Installation, configuration, data storage, troubleshooting"),
    ("Developer", "Architecture, API reference, module map, testing"),
], [2700, 6660])
doc.add_heading("Contents", level=2)
for item in [
    "1. Project overview", "2. Quick start for website users", "3. Website screen guide",
    "4. Running a search", "5. Understanding and exporting results",
    "6. GitHub, PyCharm installation, configuration, and running", "7. Data and supplementary files",
    "8. Technical architecture and API", "9. Troubleshooting", "10. Security, limits, and good practice",
    "Appendix A: Output field dictionary", "Appendix B: Administrator checklist",
]:
    bullet(doc, item)
add_callout(doc, "Important", "AI-generated classifications and extracted medical information must be reviewed by a qualified person. This application supports research; it does not provide medical advice.")

doc.add_heading("Beginner vocabulary", level=2)
add_table(doc, ["Term", "Plain-language meaning"], [
    ("Repository (repo)", "The complete project folder stored on GitHub."),
    ("Clone", "Download a working copy of the GitHub repository with Git."),
    ("PyCharm", "The program used to open, edit, and run this Python project."),
    ("Interpreter", "The Python executable PyCharm uses to run the code."),
    ("Virtual environment (.venv)", "A private Python installation for this project and its packages."),
    ("Terminal", "A text window in PyCharm where commands are entered."),
    ("Frontend", "The HTML/CSS/JavaScript page visible in the browser."),
    ("Backend / API", "The FastAPI Python server that performs searches and returns results."),
    ("Environment variable", "A private configuration value, such as an API key, read from .env."),
], [2600, 6760])

page_break(doc)
doc.add_heading("1. Project overview", level=1)
doc.add_heading("What AI Extract does", level=2)
para(doc, "AI Extract is a local web application for medical, clinical, healthcare, and life-sciences research literature discovery and evidence extraction. A user enters a medical research question. The system normalizes the wording, searches PubMed and PMC, returns papers with PMC full text, and can run OpenAI GPT-powered extraction on selected papers.")
doc.add_heading("Main capabilities", level=2)
for text in [
    "Normalizes short or detailed medical questions before searching.",
    "Handles ambiguous abbreviations by asking the user to select the intended meaning.",
    "Searches for PMCID-linked papers and supports an optional publication-year range.",
    "Retrieves metadata such as title, authors, journal, abstract, DOI, MeSH terms, keywords, and publication type.",
    "Parses PMC XML into full text, named sections, figure captions, and tables.",
    "Always classifies relevance; optionally continues with systematic literature review (SLR) detection, study design, medical codes, analysis methods, outcomes, and countries.",
    "Automatically locates and extracts available supplementary PDF, Word, Excel, PowerPoint, archive, text, and video-related files for papers analyzed by AI.",
    "Shows progress without freezing the website and exports the complete result as CSV.",
]:
    bullet(doc, text)
doc.add_heading("What the application does not do", level=2)
for text in [
    "It does not guarantee that every PubMed paper has free full text. Results are restricted to papers with a PMCID.",
    "It does not replace systematic-review quality checks, duplicate screening, risk-of-bias assessment, or clinical judgment.",
    "It does not permanently store search jobs in a database. Jobs live in server memory and are lost when the application restarts.",
    "It does not require Streamlit; the current interface is FastAPI with standard HTML, CSS, and JavaScript.",
]:
    bullet(doc, text)

page_break(doc)
doc.add_heading("2. Quick start for website users", level=1)
add_callout(doc, "Before you begin", "Ask the administrator to start the application. You need the website address, normally http://127.0.0.1:8000 on the same computer.")
step(doc, "Open the website", "Open a modern browser and go to http://127.0.0.1:8000. The top-right service indicator should say “Service online.”")
step(doc, "Enter a research question", "Use a clear medical question or keywords, for example: NSCLC pembrolizumab survival.")
step(doc, "Choose the number of papers", "Set PMC papers from 1 to 200. Start with 10 to learn the workflow.")
step(doc, "Choose optional settings", "Turn on a year filter if needed. Turn on AI extraction only when you need structured evidence.")
step(doc, "Click Find evidence", "Review the normalized query. Edit it or select the intended abbreviation meaning, then choose Confirm and search.")
step(doc, "Wait for completion", "Watch the stage, message, percentage, and progress bar. Every paper goes through full-text, supplementary, and relevance processing; advanced extraction continues from SLR through the remaining fields.")
step(doc, "Review and export", "Use View on a paper for detail, View Excel table for all fields, and Download CSV to save the results.")
add_callout(doc, "Recommended first test", "Request 5 papers with advanced AI extraction off. Confirm that full text, supplements, and relevance are present while SLR and later fields are blank. Then enable advanced extraction for 1 or 2 papers.")

page_break(doc)
doc.add_heading("3. Website screen guide", level=1)
doc.add_heading("Navigation", level=2)
add_table(doc, ["Menu item", "Where it takes you"], [
    ("Dashboard", "Top of the page and service status"),
    ("Search Papers", "Research query form"),
    ("Full Text", "Research paper results"),
    ("AI Extraction", "AI settings inside the search form"),
    ("Analytics", "Result metric cards"),
    ("Settings", "Paper count and year controls"),
], [2300, 7060])
doc.add_heading("Search controls", level=2)
add_table(doc, ["Control", "Meaning", "Allowed / default"], [
    ("Medical research query", "The question or keywords to search", "1-5,000 characters"),
    ("PMC papers", "Maximum PMCID papers requested", "1-200; default 30"),
    ("Filter by publication year", "Shows From and To fields", "Off by default"),
    ("From / To", "Inclusive publication-year range", "1900-2100"),
    ("Run advanced AI extraction agents", "Adds codes, methods, outcomes, and country extraction", "Off by default"),
    ("Papers for advanced extraction", "Maximum papers sent through the later AI agents", "1-200; default 5"),
    ("SLR papers", "Keep or remove papers classified as SLRs; enabled only with advanced extraction", "Include SLR / Exclude SLR"),
], [2400, 4560, 2400])
doc.add_heading("Status and result areas", level=2)
for text in [
    "Service status: confirms whether the backend responds.",
    "Job progress: displays queued, searching, extracting, complete, or failed state.",
    "Normalized query banner: shows the exact confirmed query and confidence.",
    "Metrics: total papers, PMC articles, unique countries, and unique medical codes.",
    "Research papers table: title/identifier, publication year, country, AI status, and View action.",
    "Extraction data sheet: spreadsheet-style display of every returned column.",
]:
    bullet(doc, text)

page_break(doc)
doc.add_heading("4. Running a search", level=1)
doc.add_heading("Write a useful question", level=2)
para(doc, "Use disease, population, treatment/exposure, and outcome terms when possible. The normalizer may convert common language to biomedical search terms.")
add_table(doc, ["Less useful", "More useful"], [
    ("diabetes study", "type 2 diabetes metformin cardiovascular outcomes"),
    ("lung cancer drug", "NSCLC pembrolizumab overall survival"),
    ("heart failure", "heart failure SGLT2 inhibitor hospitalization real-world evidence"),
], [3000, 6360])
doc.add_heading("Confirm the normalized query", level=2)
para(doc, "The application always asks for confirmation before PubMed retrieval. The dialog shows the normalized query, query style, and confidence. You may edit the text before confirming.")
for text in [
    "If an abbreviation has several medical meanings, choose the correct option.",
    "Choosing None of the above leaves no valid normalized query and stops the search until you enter one.",
    "Cancel closes the dialog and PubMed is not searched.",
    "Confirm and search records the approved query and starts a background job.",
]:
    bullet(doc, text)
doc.add_heading("Year filtering", level=2)
para(doc, "Turn on the year filter to search within an inclusive date range. Both years are required and From must not be later than To. Turn the filter off to search without a publication-year restriction.")
doc.add_heading("AI extraction choices", level=2)
add_table(doc, ["Choice", "Effect"], [
    ("Advanced extraction off", "Retrieves/parses full text and supplements and runs relevance for every returned paper, then stops. SLR, study design, code, method, outcome, and country fields remain blank."),
    ("Advanced extraction on", "Runs the baseline stages for every paper, then continues with SLR/study design, medical codes, analysis methods, outcome, and country for the configured first papers."),
    ("Include SLR", "Keeps all analyzed papers, including systematic reviews."),
    ("Exclude SLR", "Removes papers when Is_SLR is true. This option is available only when advanced extraction is on."),
], [2300, 7060])
add_callout(doc, "Cost and time", "The always-on relevance stage uses OpenAI GPT for every returned paper. Advanced extraction adds SLR and several more OpenAI API requests. Start with a small paper count and advanced-extraction limit.")

page_break(doc)
doc.add_heading("5. Understanding and exporting results", level=1)
doc.add_heading("AI status badges", level=2)
add_table(doc, ["Badge", "Meaning"], [
    ("Relevant", "AI classified the paper as relevant to the original user question."),
    ("Not relevant", "AI classified the paper as not relevant."),
    ("Not analyzed", "A legacy or incomplete result does not contain a relevance decision. In the current pipeline, baseline relevance runs for every returned paper."),
    ("Error", "Paper-level processing returned an Agent_Error."),
], [2200, 7160])
doc.add_heading("How the relevance score is obtained", level=2)
para(doc, "Relevance is evaluated by the OpenAI model from the complete meaning of the confirmed user query, the paper title, and the supplied PMC article sections (up to 60,000 characters). It is semantic AI judgment, not a keyword-count percentage and not a fixed weighted arithmetic model.")
add_table(doc, ["Input considered", "How it affects the judgment"], [
    ("Condition / disease", "Whether the paper's main clinical topic matches the question."),
    ("Treatment / comparator", "Whether the studied intervention, exposure, or comparison matches."),
    ("Population / setting", "Whether the people, care setting, or data source is applicable."),
    ("Outcome / endpoint", "Whether the paper studies the requested result or objective."),
    ("Methods / study design", "Whether the design, real-world evidence, utilization, cost, or other requested method matches."),
    ("Location of evidence", "Main-topic evidence is favored; incidental words in background or references are not sufficient."),
], [2800, 6560])
para(doc, "The model returns raw Relevant, Relevance_Score, and Relevance_Reason values. The implemented score-normalization formula is:")
p = doc.add_paragraph()
p.alignment = WD_ALIGN_PARAGRAPH.CENTER
font(p.add_run("final_score = round(max(0.0, min(raw_GPT_score, 1.0)), 4)"), 11, True, DARK)
para(doc, "Therefore a value below 0 becomes 0.0000, a value above 1 becomes 1.0000, and a valid value is rounded to four decimal places. Example: raw 0.87346 becomes 0.8735; raw 1.20 becomes 1.0000. If the value is absent or invalid, the score becomes 0.0000.")
add_callout(doc, "Boolean decision versus score", "Relevant is a separate Boolean decision returned by GPT. The code does not apply a numeric cutoff such as score >= 0.50. A paper is kept only when Relevant is exactly true. Missing/very short article sections, unavailable full text, or an agent error produce Relevant=false and score 0.0000.")
add_callout(doc, "How to get a more useful relevance score", "Write a specific query containing the condition, population, intervention/comparator, outcome, setting, and desired study design when applicable. Confirm or edit the normalized query carefully. Use papers with adequate PMC full text. The score is AI-generated and can vary; always review Relevance_Reason and the source article.", GREEN)
doc.add_heading("Paper detail window", level=2)
para(doc, "Choose View on any result row. The detail window may show journal, year, country, authors, language, relevance, links, outcome, relevance reason, analysis methods, medical codes, abstract, affiliations, MeSH terms, keywords, supplementary status, supplementary files, full text, sections, tables, figures, supplementary content, and processing errors.")
for text in [
    "Use PubMed, PMC full article, or DOI links to verify the source.",
    "Large content areas are collapsed. Select Show full text, Show tables, or similar links to expand them.",
    "Blank code, analysis, outcome, or country fields are expected when advanced extraction is off or the paper is beyond its advanced-extraction limit.",
]:
    bullet(doc, text)
doc.add_heading("Extraction data sheet", level=2)
para(doc, "Choose View Excel table to display every available field. Scroll horizontally for more columns. Long cells are shortened; click a long cell to open the complete value. This is a web table, not a saved Excel workbook.")
doc.add_heading("Download CSV", level=2)
step(doc, "Wait for completion", "The button appears only when the completed job contains at least one paper.")
step(doc, "Choose Download CSV", "The browser downloads a UTF-8 CSV named from the normalized query.")
step(doc, "Open safely", "Use Excel, LibreOffice Calc, Google Sheets, R, Python, or another analysis tool.")
add_callout(doc, "CSV safety", "Cells beginning with =, +, -, or @ are prefixed with an apostrophe to reduce spreadsheet formula-injection risk.")

page_break(doc)
doc.add_heading("6. GitHub, PyCharm installation, configuration, and running", level=1)
add_callout(doc, "Outcome", "At the end of this section, a completely new user will have the GitHub project open in PyCharm, a project-specific Python interpreter, required packages, a private .env file containing the OpenAI API key, and the website running locally.")
doc.add_heading("6.1 Install the required programs", level=2)
for text in [
    "Install Git from https://git-scm.com/downloads. Accept the standard installer choices unless your organization specifies otherwise.",
    "Install Python 3.10 or newer from https://www.python.org/downloads/. On Windows, select Add python.exe to PATH during installation.",
    "Install PyCharm Community or Professional from https://www.jetbrains.com/pycharm/download/. The free Community edition is sufficient.",
    "Restart Windows after installation if the terminal cannot find git or python.",
]:
    bullet(doc, text)
doc.add_heading("6.2 Download the project from GitHub", level=2)
para(doc, "Method A - PyCharm: open PyCharm, choose Get from VCS, select Git, paste the repository URL supplied by the project owner, choose a local directory, and select Clone. If prompted, sign in to GitHub for a private repository.")
para(doc, "Method B - terminal: replace <GITHUB_REPOSITORY_URL> and <PARENT_FOLDER> with real values.")
for command, explanation in [
    ("cd <PARENT_FOLDER>", "Move to the folder that will contain the project."),
    ("git clone <GITHUB_REPOSITORY_URL>", "Download the repository."),
    ("cd AI_extract", "Enter the cloned project folder; use its actual folder name if different."),
]:
    p = doc.add_paragraph()
    font(p.add_run(command), 10, True, DARK)
    font(p.add_run(f"\n{explanation}"), 10)
add_callout(doc, "Do not download .venv from another computer", "A virtual environment contains machine-specific paths. Create a fresh .venv after cloning. Git normally excludes it.")
doc.add_heading("6.3 Open the project correctly in PyCharm", level=2)
step(doc, "Open the repository root", "Choose File > Open and select the folder that directly contains main.py, requirements.txt, README.md, agents, parser, pubmed, web, and tests. Choose Trust Project if the source is trusted.")
step(doc, "Open the PyCharm terminal", "Choose View > Tool Windows > Terminal. The prompt should end in the project folder. All commands below are entered here, one line at a time.")
step(doc, "Create the environment", "On Windows run python -m venv .venv. On macOS/Linux run python3 -m venv .venv.")
step(doc, "Select the interpreter", "Open File > Settings > Project: AI_extract > Python Interpreter (macOS: PyCharm > Settings). Choose Add Interpreter > Add Local Interpreter > Existing, then select .venv\\Scripts\\python.exe on Windows or .venv/bin/python on macOS/Linux.")
step(doc, "Verify", "The interpreter shown by PyCharm should point inside this project's .venv, not to another project or a global Python installation.")
doc.add_heading("6.4 Install the Python packages", level=2)
para(doc, "With the project interpreter selected, use the PyCharm terminal:")
for command, explanation in [
    ("python -m pip install --upgrade pip", "Update pip inside .venv."),
    ("python -m pip install -r requirements.txt", "Install FastAPI, Uvicorn, OpenAI, parsing, spreadsheet, document, and testing dependencies."),
    ("python -m pip check", "Confirm installed package requirements are consistent."),
]:
    p = doc.add_paragraph()
    font(p.add_run(command), 10, True, DARK)
    font(p.add_run(f"\n{explanation}"), 10)
doc.add_heading("6.5 Create .env and upload/add the GPT API key", level=2)
add_callout(doc, "Where the key goes", "The GPT/OpenAI API key is not uploaded through the website. Put it in a file named .env in the project root, beside main.py and config.py. Never put the real key in .env.example, Python code, GitHub, chat, screenshots, or this manual.", RED)
step(doc, "Create the file", "In PyCharm's Project panel, right-click the project root > New > File > type .env. Alternatively, in Windows PowerShell run Copy-Item .env.example .env; on macOS/Linux run cp .env.example .env.")
step(doc, "Get an OpenAI API key", "Use your authorized OpenAI Platform account and project. Create/copy a secret API key and ensure billing/usage limits and model access are configured. A ChatGPT subscription alone is not the same as API credit.")
step(doc, "Enter private values", "Open .env and use the exact format below, with no quotes and no spaces around =. Replace the sample email and placeholder with real values.")
p = doc.add_paragraph()
font(p.add_run("NCBI_EMAIL=your_real_email@example.com\nNCBI_API_KEY=\nOPENAI_API_KEY=sk-your-private-key\nAI_EXTRACT_HOST=127.0.0.1\nAI_EXTRACT_PORT=8000\nAI_EXTRACT_MAX_WORKERS=2\nPAPER_PROCESS_MAX_WORKERS=3\nDETAILED_AGENT_MAX_WORKERS=3"), 9.5, True, DARK)
step(doc, "Save and restart", "Save .env. Stop a running server with Ctrl+C and start it again, because configuration is loaded when Python imports the project.")
step(doc, "Confirm Git protection", "The supplied .gitignore excludes .env. Before every commit, check that .env is not listed by git status. If a real key is ever committed, revoke/rotate it immediately; deleting the line later does not remove it from Git history.")
doc.add_heading("6.6 Create a PyCharm run configuration", level=2)
step(doc, "Open configurations", "Choose Run > Edit Configurations, select +, then Python.")
step(doc, "Name it", "Use AI Extract Web Server.")
step(doc, "Choose the script", "Set Script path to the project's main.py.")
step(doc, "Set the working directory", "Set Working directory to the repository root containing main.py. Leave Parameters empty.")
step(doc, "Choose Python", "Select the project's .venv interpreter, enable Add content roots to PYTHONPATH if shown, then Apply and OK.")
step(doc, "Run", "Select AI Extract Web Server and click the green Run triangle. The Run window should show Uvicorn listening on http://127.0.0.1:8000.")
doc.add_heading("6.7 Complete command list", level=2)
add_table(doc, ["Task", "Windows PowerShell", "macOS / Linux"], [
    ("Clone", "git clone <URL>", "git clone <URL>"),
    ("Enter project", "cd AI_extract", "cd AI_extract"),
    ("Create environment", "python -m venv .venv", "python3 -m venv .venv"),
    ("Activate (optional in PyCharm)", ".\\.venv\\Scripts\\Activate.ps1", "source .venv/bin/activate"),
    ("Install", "python -m pip install -r requirements.txt", "python -m pip install -r requirements.txt"),
    ("Create .env", "Copy-Item .env.example .env", "cp .env.example .env"),
    ("Run server", "python main.py", "python main.py"),
    ("Run tests", "python -m unittest discover -s tests -v", "python -m unittest discover -s tests -v"),
    ("Stop server", "Ctrl+C", "Ctrl+C"),
], [1900, 3730, 3730])
add_callout(doc, "PowerShell activation error", "If Activate.ps1 is blocked, activation is optional: after PyCharm selects .venv, use python commands in its terminal, or run .\\.venv\\Scripts\\python.exe main.py directly. Do not weaken the computer-wide execution policy just for this project.")
doc.add_heading("Requirements", level=2)
for text in [
    "Windows, macOS, or Linux with Python 3.10+ recommended.",
    "Internet access to NCBI/PubMed/PMC, Europe PMC or publisher sources for supplements, OpenAI, and the external font/icon CDNs used by the interface.",
    "A valid contact email for NCBI. An NCBI API key is optional but recommended for higher request limits.",
    "An OpenAI API key is required for query normalization and AI extraction.",
]:
    bullet(doc, text)
doc.add_heading("Set up the project on Windows PowerShell", level=2)
for command, explanation in [
    ("cd C:\\AI_extract", "Move into the project folder."),
    ("python -m venv .venv", "Create a local Python environment if it does not already exist."),
    (".\\.venv\\Scripts\\Activate.ps1", "Activate the environment."),
    ("python -m pip install -r requirements.txt", "Install required packages."),
    ("Copy-Item .env.example .env", "Create a private configuration file."),
]:
    p = doc.add_paragraph()
    font(p.add_run(command), 10, True, DARK)
    font(p.add_run(f"\n{explanation}"), 10)
doc.add_heading("Configure .env", level=2)
add_table(doc, ["Variable", "Purpose", "Example / default"], [
    ("NCBI_EMAIL", "Contact email sent with NCBI requests", "your_email@example.com"),
    ("NCBI_API_KEY", "Optional NCBI API key", "Leave blank if unavailable"),
    ("OPENAI_API_KEY", "OpenAI authentication for normalization and AI extraction", "Required for normal use"),
    ("AI_EXTRACT_HOST", "Server interface", "127.0.0.1"),
    ("AI_EXTRACT_PORT", "Local HTTP port", "8000"),
    ("AI_EXTRACT_MAX_WORKERS", "Concurrent background search jobs", "2; minimum 1"),
    ("PAPER_PROCESS_MAX_WORKERS", "Parallel baseline paper processing", "3; capped at 5"),
    ("DETAILED_AGENT_MAX_WORKERS", "Parallel detailed agents inside one paper", "3; capped at 5"),
], [2350, 4240, 2770])
add_callout(doc, "Protect secrets", "Never commit .env or API keys to Git, share screenshots containing keys, or place real keys in documentation. The project can temporarily read older .streamlit/secrets.toml values, but Streamlit itself is not used.")

page_break(doc)
doc.add_heading("Starting and stopping the website", level=2)
para(doc, "From C:\\AI_extract, run:")
p = doc.add_paragraph()
font(p.add_run(".\\.venv\\Scripts\\python.exe main.py"), 11, True, DARK)
para(doc, "Open http://127.0.0.1:8000. Interactive API documentation is at http://127.0.0.1:8000/api/docs.")
para(doc, "When PyCharm has selected .venv, the portable command is python main.py. On Windows, .\\.venv\\Scripts\\python.exe main.py works even without environment activation. Wait for the application startup message before opening the browser.")
doc.add_heading("Stop the server", level=2)
para(doc, "Return to the terminal where it is running and press Ctrl+C. Any in-memory job history will be lost.")
doc.add_heading("Network access", level=2)
para(doc, "The default host 127.0.0.1 accepts connections only from the same computer. Changing the host to 0.0.0.0 can expose the service to the local network. Do this only with proper firewall rules, authentication, TLS/reverse proxy, and organizational approval; the application has no built-in user authentication.")
doc.add_heading("Dependency summary", level=2)
add_table(doc, ["Area", "Packages"], [
    ("Web/API", "FastAPI, Uvicorn"),
    ("PubMed/PMC", "Biopython, requests, BeautifulSoup, lxml"),
    ("AI", "openai"),
    ("Data", "pandas"),
    ("Files", "PyMuPDF, python-docx, python-pptx, openpyxl, xlrd"),
    ("Configuration", "python-dotenv"),
], [2200, 7160])

page_break(doc)
doc.add_heading("7. Data and supplementary files", level=1)
doc.add_heading("Where supplementary data is stored", level=2)
para(doc, "Downloaded and extracted supplementary checkpoints are versioned under:")
p = doc.add_paragraph()
font(p.add_run("data\\supplementary_materials\\<PMCID>\\"), 11, True, DARK)
para(doc, "Each analyzed paper can have its own folder. Exact files depend on what PMC, Europe PMC, or a supported publisher makes available.")
doc.add_heading("Supported supplementary content", level=2)
for text in [
    "PDF documents", "Word documents", "Excel workbooks and older XLS files",
    "PowerPoint files", "ZIP or other supported archives", "Text/CSV-type files",
    "Video-related supplementary files where discoverable",
]:
    bullet(doc, text)
doc.add_heading("Supplementary status", level=2)
para(doc, "Supplementary_Status explains whether files were found, downloaded, extracted, not available, or failed. Supplementary_Files contains structured file results. Supplementary_Content contains extracted text and may be truncated for safe processing/display.")
add_callout(doc, "Storage warning", "Supplementary files can consume significant disk space and may contain publisher-provided content. Follow license, privacy, and retention requirements before copying or sharing them.")

page_break(doc)
doc.add_heading("8. Technical architecture and API", level=1)
doc.add_heading("How a request moves through the system", level=2)
for text in [
    "Browser sends the user question to POST /api/normalize.",
    "OpenAI GPT normalizes the query and may return abbreviation choices.",
    "After confirmation, POST /api/search creates a background job.",
    "The browser polls GET /api/jobs/{job_id} once per second.",
    "The server searches PubMed, resolves PMC links, and falls back to a direct PMC search when needed.",
    "Each candidate paper is downloaded and parsed, then assessed for relevance. Irrelevant papers stop before supplementary and detailed extraction.",
    "Relevant papers retrieve supplementary material. When advanced extraction is enabled, the configured papers also run SLR, evidence, medical-code, analysis-method, outcome, and country agents.",
    "Results are returned to the page and can be exported through GET /api/jobs/{job_id}/download.",
]:
    step(doc, f"Stage {len(doc.paragraphs)}", text)
doc.add_heading("Main project modules", level=2)
add_table(doc, ["Path", "Responsibility"], [
    ("main.py", "FastAPI app, validation, job management, progress, metrics, CSV download"),
    ("config.py", ".env loading and legacy secret fallback"),
    ("web/", "Website HTML, CSS, and browser-side JavaScript"),
    ("pubmed/", "Query building, PubMed search, metadata, PMCID mapping, downloading"),
    ("parser/", "PMC XML parsing, cleaning, figures, tables, supplementary discovery/extraction"),
    ("agents/", "OpenAI client and normalization, relevance, SLR, code, method, outcome/country, and SAP agents"),
    ("utils/", "Retry, progress, and helper utilities"),
    ("tests/", "Web, supplementary, and agent/notebook regression tests"),
], [2500, 6860])
doc.add_heading("API endpoints", level=2)
add_table(doc, ["Method and path", "Purpose", "Common response"], [
    ("GET /", "Serve the website", "HTML"),
    ("GET /api/health", "Service check", '{"status":"ok"}'),
    ("POST /api/normalize", "Normalize and validate a medical query", "Normalization JSON"),
    ("POST /api/search", "Create a confirmed search job", "202 + job_id"),
    ("GET /api/jobs/{job_id}", "Read job state/results", "Job JSON or 404"),
    ("GET /api/jobs/{job_id}/download", "Download completed result", "CSV; 409 if not ready"),
], [3000, 4100, 2260])

page_break(doc)
doc.add_heading("9. Troubleshooting", level=1)
add_table(doc, ["Problem", "Likely cause", "What to do"], [
    ("Page does not open", "Server is stopped, wrong port, or firewall issue", "Start main.py; confirm the terminal shows no fatal error; open the configured host/port."),
    ("Service unavailable", "Health request failed", "Refresh; check terminal output; confirm /api/health returns status ok."),
    ("Query normalization failed", "Missing/invalid OpenAI key, network issue, or OpenAI API error", "Check OPENAI_API_KEY and internet access; restart after editing .env."),
    ("Not recognized as a valid medical query", "Question is non-medical or too vague", "Add disease, treatment, population, outcome, or biomedical terms."),
    ("No PMC papers found", "Query is narrow or papers lack PMCID", "Broaden terms, remove/reduce year filtering, request fewer papers."),
    ("Search is slow", "Every paper retrieves full text/supplements and runs relevance; advanced agents add SLR and later work", "Reduce paper count and advanced-extraction count; add NCBI key; wait for progress."),
    ("Advanced fields are blank", "Advanced extraction is off, beyond its limit, no full text, or no evidence was found", "Check the toggle, advanced paper limit, processing error, and full text."),
    ("Exclude SLR seems ineffective", "Is_SLR was false/unclear or processing failed", "Review Is_SLR, Study_Design, relevance, and processing errors in the full table."),
    ("Download button missing", "Job incomplete or zero results", "Wait for completion or run a broader search."),
    ("CSV looks garbled", "Wrong import encoding", "Import as UTF-8; the file includes a UTF-8 BOM for Excel."),
    ("Port already in use", "Another service is using 8000", "Set AI_EXTRACT_PORT to another unused port, then restart."),
    ("Fonts/icons missing", "CDN blocked or offline", "Core functions still work; allow fonts.googleapis.com and cdnjs.cloudflare.com if policy permits."),
], [2300, 2960, 4100])
doc.add_heading("Administrator diagnostic checks", level=2)
for text in [
    "Open /api/health and confirm {\"status\":\"ok\"}.",
    "Open /api/docs to test and inspect the API schema.",
    "Review terminal errors without copying API keys into support messages.",
    "Run the automated test suite: .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v",
]:
    bullet(doc, text)

page_break(doc)
doc.add_heading("10. Security, limits, and good practice", level=1)
for text in [
    "Do not enter patient names, direct identifiers, confidential records, or protected health information unless your organization has explicitly approved the complete data flow.",
    "Queries and extracted paper text may be sent to OpenAI when normalization or AI extraction is used. Review your organization’s data-processing rules.",
    "The service has no login, role controls, persistent audit log, or encryption configuration. Keep the default loopback host for personal/local use.",
    "Review source articles before using extracted outcomes, countries, codes, study designs, or methods.",
    "Respect NCBI usage rules and provide a real NCBI contact email. Use an NCBI API key for sustained higher-volume use.",
    "Keep paper count, worker count, and AI analysis count appropriate for your API limits, machine capacity, and cost controls.",
    "Back up only the data you are permitted to retain. Search jobs are temporary, while supplementary files remain on disk.",
]:
    bullet(doc, text)
add_callout(doc, "Quality rule", "Treat every AI field as a lead to verify, not as final evidence. Use the PMC article, PubMed record, DOI page, and extracted full-text sections for confirmation.", GREEN)

page_break(doc)
doc.add_heading("Appendix A: Output field dictionary", level=1)
rows = [
    ("PMCID / PMID", "PMC and PubMed identifiers"),
    ("Title / Journal / PublicationYear", "Core citation information"),
    ("Authors / Affiliations / Language", "Authorship and publication context"),
    ("DOI / PubMedURL / PMCURL", "Source identifiers and verification links"),
    ("Abstract", "PubMed abstract when available"),
    ("MeSH Terms / Keywords", "Indexing and author keywords"),
    ("Publication Types / Chemical List", "PubMed publication and substance metadata"),
    ("Relevant", "AI Boolean relevance classification"),
    ("Relevance_Score", "AI relevance confidence/score"),
    ("Relevance_Reason", "Short explanation supporting relevance decision"),
    ("Is_SLR", "True, false, or unclear systematic-review classification"),
    ("Study_Design", "Concise AI-derived design label"),
    ("ICD_9_CM / ICD_10_CM / ICD_10_PCS", "Diagnosis and procedure code evidence"),
    ("CPT / HCPCS / NDC", "Procedure/service and drug code evidence"),
    ("Analysis", "Analysis methods detected in article/supporting material"),
    ("Outcome", "Primary outcome or explicit fallback text"),
    ("Country", "Study-data country/countries, not necessarily author location"),
    ("Full_Text", "Text assembled from parsed sections, figures, and tables"),
    ("Sections / Figures / Tables", "Structured PMC XML extracts"),
    ("Supplementary_Status", "Supplement retrieval/extraction result"),
    ("Supplementary_Files", "Structured records for discovered supplement files"),
    ("Supplementary_Content", "Text extracted from supplementary files"),
    ("*_Agent_Error", "Agent-specific diagnostic error"),
]
add_table(doc, ["Field", "Meaning"], rows, [3300, 6060])

page_break(doc)
doc.add_heading("Appendix B: Administrator checklist", level=1)
doc.add_heading("Before first use", level=2)
for text in [
    "Create and activate .venv.", "Install requirements.txt.", "Create .env from .env.example.",
    "Set a real NCBI_EMAIL.", "Set OPENAI_API_KEY.", "Optionally set NCBI_API_KEY.",
    "Keep AI_EXTRACT_HOST=127.0.0.1 unless network deployment is secured.",
    "Run the test suite.", "Start main.py and verify /api/health.", "Perform a 5-paper baseline test with advanced extraction off.",
    "Confirm full text, supplementary status, and relevance while SLR/later fields are blank, then perform a 1-paper advanced extraction test.",
]:
    bullet(doc, text)
doc.add_heading("Routine operation", level=2)
for text in [
    "Monitor disk space under data\\supplementary_materials.",
    "Review API usage and rate-limit errors.",
    "Keep dependencies and API clients updated through controlled testing.",
    "Do not publish the service directly to the internet.",
    "Retest CSV export and paper detail display after code changes.",
]:
    bullet(doc, text)
doc.add_heading("Acceptance check", level=2)
add_callout(doc, "Ready for users", "The service is online, a normalized query can be confirmed, results appear, paper detail opens, the full data table works, CSV downloads, and an AI test paper shows a reviewable result or a clear error.")

doc.core_properties.title = "AI Extract Complete User Manual and Project Documentation"
doc.core_properties.subject = "User guide, installation guide, administrator reference, and technical overview"
doc.core_properties.author = "AI Extract Project"
doc.core_properties.keywords = "AI Extract, PubMed, PMC, OpenAI GPT, user manual, health research evidence"
doc.save(OUT)
print(OUT)
