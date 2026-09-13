# MedEvidence Hub

## Deploy on Render

Create a **Python Web Service** from this repository, or update the settings of
an existing service:

| Setting | Value |
| --- | --- |
| Root Directory | `MedEvidence Hub` |
| Build Command | `python -m pip install -r requirements.txt` |
| Start Command | `uvicorn server:app --host 0.0.0.0 --port $PORT` |

The repository's `.python-version` selects Python 3.13. Add `NCBI_EMAIL` and
`OPENAI_API_KEY` in the Render environment settings, and `NCBI_API_KEY` if you
have one. Do not commit API keys. An existing Render Web Service does not pick
up these dashboard settings from this README; save the values in its Settings
page and redeploy.

CSV datasets are intentionally excluded from GitHub. The Code Lookup page can
open without them, but diagnosis, procedure, and NDC searches remain
unavailable until the datasets are provided in its `data` directory. Loading
the full datasets into memory can exceed Render's 512 MB free instance limit.

User-added lookup records and generated research files are written to local
files. Render's default filesystem does not preserve those files across
restarts or deploys, so use persistent storage before relying on them.

MedEvidence Hub combines two local applications in one website:

- **Intelligent Code Lookup**: diagnosis, procedure, drug, and NDC code search.
- **Evidence Synthesis**: Europe PMC retrieval and AI-assisted research extraction.

Run both applications together from this project directory:

```powershell
cd "D:\Code_extract\MedEvidence Hub"
.\.hub-venv\Scripts\python.exe server.py
```

Open <http://127.0.0.1:5000>. The Hub routes users to `/code-lookup/` or
`/evidence-synthesis/` while preserving each application's existing features.

## Intelligent Code Lookup

MedCode Finder is a local web application for searching diagnosis, procedure, and drug/NDC records stored in CSV files. The browser interface runs against a Python/Flask server on your computer; the application does not call an external search API.

## Quick start

### Requirements

- Python 3.10 or newer
- A modern web browser
- CSV datasets containing the columns described below

### Install and run

To create the compatible Hub environment on another computer, use Python 3.10
or newer:

```powershell
cd "D:\Code_extract\MedEvidence Hub"
python -m venv .hub-venv
.\.hub-venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python server.py
```

Then open <http://127.0.0.1:5000>.

Select **Manage datasets** to view read-only parent record counts or add a separate user record. Enter a term or code, select one or more datasets, and choose **Search records**.

## Required dataset columns

| Dataset | Required columns | Searched columns | Stored filename |
| --- | --- | --- | --- |
| Diagnosis | `Description` | `Description` and optional `code`/`codes` | `data/diagnosis_codes.csv` |
| Procedure | `Description` | `Description` and optional `code`/`codes` | `data/procedure_codes.csv` |
| Drug / NDC | `NDC`, `PROPRIETARYNAME`, `NONPROPRIETARYNAME`, `SUBSTANCENAME` | `NDC` and all three name/substance columns | `data/lu_ndc(in).csv` |

Parent datasets are administrator-managed files in `data` and cannot be replaced through the browser. Users can add one record or bulk-import a schema-matching CSV. User-added records are stored separately in `uploads/diagnosis/user_records.csv`, `uploads/procedure/user_records.csv`, or `uploads/ndc/user_records.csv`; searches include both sources.

## Full documentation

See the [User Manual](docs/USER_MANUAL.md) for complete installation, dataset preparation, searching, terminology expansion, result interpretation, troubleshooting, privacy, and administration instructions.

## Important notice

This application is a lookup aid, not a clinical decision system. Verify codes against the authoritative code set and current organizational guidance before using them for care, billing, reporting, or compliance.
