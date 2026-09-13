# AI Extract

AI Extract is a local web application for searching Europe PMC, retrieving PMC
full text and supplementary materials, and extracting structured evidence from
medical, clinical, healthcare, and life-sciences research literature with OpenAI GPT.

The frontend uses standard HTML, CSS, and JavaScript. FastAPI serves the
frontend and runs searches as background jobs so long literature and AI
processing does not freeze the page.

Before Europe PMC retrieval, the application shows the normalized query for user
confirmation or editing. Ambiguous medical abbreviations present selectable
meanings, and cancelling or choosing none stops the search.

Every returned paper is processed through PMC full-text and supplementary
material retrieval and relevance assessment. This baseline runs even when
advanced AI extraction is off. Enabling advanced extraction continues from SLR
detection and study-design classification through medical-code,
analysis-method, outcome, and country extraction for the configured number of
papers. When advanced extraction is enabled, searches can include SLR papers
or exclude papers classified as systematic literature reviews.

## Features

- medical-query normalization for Europe PMC retrieval;
- PMCID paper search with optional publication-year filters;
- metadata, full text, sections, figures, and tables;
- always-on full text, supplementary retrieval, and relevance assessment;
- optional advanced SLR identification, study-design, medical-code,
  analysis-method, outcome, and country extraction;
- supplementary PDF, Word, Excel, PowerPoint, archive, text, and video files;
- live progress, paper detail views, result metrics, and CSV download; and
- optional one-document, evidence-informed Statistical Analysis Plan (SAP)
  synthesized from every successfully extracted relevant paper, with a JSON
  download and explicit requested, returned, and contributing-paper counts;
- versioned supplementary checkpoints under
  `data/supplementary_materials/<PMCID>/`.

## Configuration

Copy `.env.example` to `.env` and provide:

```dotenv
NCBI_EMAIL=your_email@example.com
NCBI_API_KEY=
OPENAI_API_KEY=
```

Existing `.streamlit/secrets.toml` values remain readable temporarily for
backward compatibility, but Streamlit is no longer installed or used.

## Run

```powershell
cd C:\AI_extract
.\.venv\Scripts\python.exe main.py
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Interactive API documentation is available at
[http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs).


Stop-Process -Id 21436
.\.venv\Scripts\python.exe main.py
