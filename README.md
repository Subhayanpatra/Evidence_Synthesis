# MedCode Finder

MedCode Finder is a local web application for searching diagnosis, procedure, and drug/NDC records stored in CSV files. The browser interface runs against a Python/Flask server on your computer; the application does not call an external search API.

## Quick start

### Requirements

- Python 3.10 or newer
- A modern web browser
- CSV datasets containing the columns described below

### Install and run

Open PowerShell in the project directory and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python app.py
```

Then open <http://127.0.0.1:5000>.

Select **Manage datasets**, upload the CSV files you want to search, enter a term or code, select one or more datasets, and choose **Search records**.

## Required dataset columns

| Dataset | Required columns | Searched columns | Stored filename |
| --- | --- | --- | --- |
| Diagnosis | `Description` | `Description` and optional `code`/`codes` | `data/diagnosis_codes.csv` |
| Procedure | `Description` | `Description` and optional `code`/`codes` | `data/procedure_codes.csv` |
| Drug / NDC | `NDC`, `PROPRIETARYNAME`, `NONPROPRIETARYNAME`, `SUBSTANCENAME` | `NDC` and all three name/substance columns | `data/lu_ndc(in).csv` |

Uploaded CSV files may use UTF-8, Windows-1252, or Latin-1 encoding and may be up to 250 MB each. An uploaded file is copied into the local `data` directory under the fixed filename shown above.

## Full documentation

See the [User Manual](docs/USER_MANUAL.md) for complete installation, dataset preparation, searching, terminology expansion, result interpretation, troubleshooting, privacy, and administration instructions.

## Important notice

This application is a lookup aid, not a clinical decision system. Verify codes against the authoritative code set and current organizational guidance before using them for care, billing, reporting, or compliance.
