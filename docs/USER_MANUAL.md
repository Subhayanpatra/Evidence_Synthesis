# MedCode Finder User Manual

## 1. About MedCode Finder

MedCode Finder searches medical-code reference files stored on the same computer as the application. A single query can search:

- Diagnosis descriptions, such as ICD-9 or ICD-10 descriptions
- Procedure descriptions, such as HCPCS descriptions
- Drug names and substances in an NDC reference file

The application consists of a browser interface and a local Flask server. The server loads CSV files into memory and performs the search. It does not query a remote terminology service or automatically download official code sets.

> **Medical and coding notice:** Results are only as accurate and current as the CSV files supplied to the application. MedCode Finder is for lookup assistance only. Always verify a result against an authoritative, current source before clinical, billing, reporting, or compliance use.

## 2. Before you begin

You need:

- Python 3.10 or newer
- PowerShell or another command-line terminal
- A current browser such as Edge, Chrome, or Firefox
- At least one compatible CSV dataset
- Enough memory to load the selected CSV files; pandas loads each complete file into memory

An internet connection is not required after Python and the dependencies have been installed.

## 3. Installation

### Windows PowerShell

1. Open PowerShell in the project folder.
2. Create a virtual environment:

   ```powershell
   python -m venv .venv
   ```

3. Activate it:

   ```powershell
   .\.venv\Scripts\Activate.ps1
   ```

4. Install the required packages:

   ```powershell
   python -m pip install -r requirements.txt
   ```

If PowerShell blocks activation, you may use the virtual environment without activating it:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app.py
```

The required packages and tested versions are listed in `requirements.txt`.

## 4. Starting and stopping the application

### Start

With the virtual environment active, run:

```powershell
python app.py
```

The terminal should report that the server is available at `http://127.0.0.1:5000`. Open that address in a browser. Keep the terminal open while using the application.

The address `127.0.0.1` is the loopback address, so the development server is reachable only from the same computer under the default configuration.

### Stop

Return to the terminal and press `Ctrl+C`. Closing the browser tab alone does not stop the Python server.

### Development-server warning

The included launch command uses Flask's debug development server. It is suitable for local, trusted use. Do not expose it directly to a network or the public internet. A production deployment needs debug mode disabled, a production WSGI server, authentication, access controls, and an appropriate security review.

## 5. Preparing datasets

Each dataset must be a comma-separated values (`.csv`) file. Column names are case-sensitive and must match the names below exactly. Extra columns are allowed and will be displayed in results.

### Diagnosis dataset

Required column:

```text
Description
```

Example:

```csv
Code,Description
E11.9,Type 2 diabetes mellitus without complications
I10,Essential (primary) hypertension
```

### Procedure dataset

Required column:

```text
Description
```

Example:

```csv
Code,Description
99213,Office or other outpatient visit
```

Diagnosis and procedure searches inspect only the `Description` column. A code stored in a separate `Code` column is displayed in matching rows, but the current application does not search that separate column. To make codes searchable, include the code in `Description` or modify the application search configuration.

### Drug / NDC dataset

Required columns:

```text
PROPRIETARYNAME
NONPROPRIETARYNAME
SUBSTANCENAME
```

Example:

```csv
PRODUCTNDC,PROPRIETARYNAME,NONPROPRIETARYNAME,SUBSTANCENAME
0000-0001,Example Brand,example generic,EXAMPLE INGREDIENT
```

The application searches the combined text of all three required name/substance columns. Other columns, such as the NDC identifier, appear in results but are not searched unless their value is also present in one of the three searchable columns.

### File size and encoding

- The maximum request size is 250 MB per upload.
- Supported encodings are UTF-8 (including UTF-8 with BOM), Windows-1252, and Latin-1.
- The application expects comma-separated content. A tab- or semicolon-delimited file should be converted to CSV first.
- Very large files take longer to upload, parse, and search and require more RAM.

## 6. Loading and replacing datasets

1. Open MedCode Finder in the browser.
2. Select **Manage datasets**. The panel opens automatically when one or more datasets are missing.
3. Find the card for **Diagnosis codes**, **Procedure codes**, or **NDC codes**.
4. Select **Choose CSV** and pick the corresponding file.
5. Wait for the card to show the number of loaded records.
6. Repeat for any other datasets you want to use.

The uploaded file is copied to the project's `data` directory using a fixed internal filename. Its original filename is not retained. Uploading another file for the same dataset replaces the previous file after the new upload is accepted.

If validation fails, the application reports the missing column or parsing error and does not keep the invalid upload. Correct the source CSV and upload it again.

On later starts, the server automatically loads valid files already present in `data`; it is not necessary to upload them again.

## 7. Searching

1. Enter a disease, procedure, drug name, substance, or other searchable text in the search box.
2. Under **Search in**, select at least one dataset.
3. Select **Search records**.
4. Review the summary counts and the result table for each selected, available dataset.

Search behavior:

- Matching is case-insensitive: `aspirin` and `ASPIRIN` are equivalent.
- Search text is treated literally. Characters such as `+`, `(`, or `.` are not interpreted as regular-expression instructions.
- A match must have non-word boundaries around the query. For example, searching `cat` does not match the `cat` characters inside `cataract`.
- The entire entered phrase is searched as one term; the application does not independently require every typed word.
- Diagnosis and procedure searches inspect `Description`.
- Drug/NDC searches inspect the three combined name and substance fields.
- Searches do not use fuzzy spelling, stemming, ranking, or clinical reasoning.

If a selected dataset is not loaded, the search continues in the available datasets and a message identifies the missing one.

### Broad searches and the result limit

The summary shows the full number of matches found. To keep the browser responsive, each result table displays only the first 500 matching records. When this happens, the table header says **first 500 shown**. The current interface does not paginate or export the remaining results; use a more specific query to narrow the set.

### No results

If a table says **No matching records found**:

- Confirm that the correct dataset was selected and loaded.
- Try a shorter or more general phrase.
- Check spelling and punctuation.
- Inspect the source file to ensure the expected wording is in a searchable column.
- Remember that code-only columns in diagnosis/procedure files and identifier-only columns in NDC files are not searched by default.

## 8. Medical terminology expansion

MedCode Finder can expand recognized abbreviations or terminology when this optional file exists:

```text
data/medical_terms.csv
```

It must contain these exact columns:

```text
Text,Short_Term,Long_Term,Search_Terms
```

Example:

```csv
Text,Short_Term,Long_Term,Search_Terms
Chronic obstructive pulmonary disease,COPD,Chronic obstructive pulmonary disease,COPD;chronic obstructive pulmonary disease
```

Expansion rules:

1. The entered query is compared with `Short_Term` and `Long_Term` using an exact, case-insensitive comparison.
2. When a row matches, each semicolon-separated value in `Search_Terms` is searched.
3. The short and long terms are also added to the search, with duplicates removed.
4. If there is no exact match, the original query is used unchanged.

Blank or malformed terminology files are ignored. Expansion may increase the result count because a row is returned when any expanded term matches. The `/abbreviations/<term>` endpoint can be used to inspect the resolved options, while the normal `/search` request applies expansion automatically.

## 9. Understanding results

The results area contains:

- The query and, when applicable, the terms used after expansion
- A summary card with the total match count for each searched dataset
- A table containing every column from the uploaded CSV
- A truncation notice when more than 500 rows matched

Empty CSV cells appear as blank cells in the browser. Result order follows the row order in the uploaded file; the application does not sort by relevance.

## 10. Data storage, privacy, and security

- Uploaded datasets are stored in the local project `data` directory.
- Search requests are processed by the local Flask server.
- The application code does not send datasets or queries to an external API.
- Data remains on disk after the server stops and is reloaded on the next start.
- Anyone with access to the computer and project directory may be able to read the uploaded CSV files.

Do not load protected health information or other sensitive data unless the computer, user accounts, storage, backups, and operating procedures meet your organization's requirements. This application does not provide user authentication, encryption at rest, an audit trail, role-based permissions, or automatic retention/deletion controls.

To remove a dataset, stop the server and delete only its corresponding file from `data`, then restart the server:

- `diagnosis_codes.csv`
- `procedure_codes.csv`
- `lu_ndc(in).csv`

Keep `data/.gitkeep`; it preserves the otherwise empty directory in source control. Dataset CSV files are excluded by the repository's `.gitignore` configuration, but you should still verify staged files before committing.

## 11. Troubleshooting

### The page does not open

- Confirm `python app.py` is still running.
- Use exactly `http://127.0.0.1:5000` rather than an HTTPS address.
- Look in the terminal for a Python error.
- If port 5000 is already occupied, stop the other process or change the port in the last line of `app.py`.

### `ModuleNotFoundError` appears

Activate the intended virtual environment and reinstall dependencies:

```powershell
python -m pip install -r requirements.txt
```

### A required column was not found

Open the CSV and compare its header row with the required column names. Remove leading/trailing spaces and preserve capitalization. For NDC data, all three required columns must exist even if some cells are blank.

### The CSV fails to load or has the wrong columns

Confirm that it is a real comma-delimited CSV, not an Excel workbook renamed with a `.csv` extension. Export it from the source application as CSV and try again.

### Text has unusual characters

Re-export the CSV as UTF-8. The loader attempts several common encodings, but it cannot repair every mixed or incorrectly labeled encoding.

### Search is slow

- Use a more specific query.
- Search fewer datasets at once.
- Close other memory-intensive programs.
- Reduce the source files to the columns and rows needed for lookup.

### Changes to a file in `data` are not visible

Files are loaded into memory when the server starts or when they are uploaded through the interface. If a file was edited directly on disk, restart the server to reload it.

### Dataset manager immediately reopens

This is expected when any of the three dataset types is missing or invalid. You can close the panel and search only the loaded datasets.

## 12. Backup and updates

To back up the application configuration and data, stop the server and copy the project folder to an approved secure location. Treat copies of the `data` directory according to the sensitivity of the underlying datasets.

When replacing a code set:

1. Obtain the new dataset from an authoritative source.
2. Confirm that the required columns are present.
3. Keep a backup if your retention policy requires it.
4. Upload the new CSV from **Manage datasets**.
5. Confirm the reported row count and run several known searches.
6. Record the dataset version and effective date outside the application; MedCode Finder does not track them automatically.

## 13. Technical reference

### Project layout

```text
app.py                         Flask server, loading, validation, and search
requirements.txt              Python dependencies
templates/index.html          Browser page structure
static/css/style.css          Interface styling
static/js/app.js              Upload, search, and result interactions
data/                          Locally stored CSV files
scripts/import_abbreviations.py  Legacy/helper catalog-import script
docs/USER_MANUAL.md           This manual
```

### Local HTTP endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Display the application |
| `GET` | `/status` | Return dataset availability, row counts, and load errors |
| `GET` | `/abbreviations/<term>` | Show terminology resolution for a term |
| `POST` | `/upload` | Validate, store, and load a CSV dataset |
| `POST` | `/search` | Search selected loaded datasets |

The endpoints are intended for the bundled local interface. They have no authentication and should not be exposed to untrusted clients.

### Search API example

Request body:

```json
{
  "keyword": "hypertension",
  "datasets": ["diagnosis", "procedure"]
}
```

The response includes the original keyword, resolved search terms, match summaries, result columns and rows, truncation indicators, and any selected datasets that were unavailable.

## 14. Limitations

- The app does not supply or update medical-code datasets.
- It does not validate whether a code is current, billable, appropriate, or clinically correct.
- It does not search every displayed column.
- It does not provide fuzzy search, relevance ranking, filters, pagination, or export.
- It displays at most 500 rows per dataset per search.
- It is designed for one local user and has no multi-user concurrency or access-control model.
- Terminology expansion relies entirely on the optional local mapping file.

These limitations should be considered before adapting the application to a production or regulated workflow.
