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
codes,Description
99213,Office or other outpatient visit
```

Diagnosis and procedure searches inspect `Description` plus any code column named `code` or `codes`. Code-column detection is case-insensitive, so `Code`, `CODE`, and `codes` are supported. The `Description` column remains required. A user can search with either a description such as `hypertension` or a code such as `001`, `I10`, or `99213`.

Code searches containing at least three characters use prefix matching. For example, `I63` returns `I63`, `I630`, `I631`, `I632`, and other codes beginning with `I63`; `K85` returns codes beginning with `K85`; and `002` returns `002`, `0020`, `0021`, and related prefixes. Leading zeros are significant, so enter `002`, not `2`. Inputs shorter than three characters use exact-code matching to prevent excessively broad results. Digits-only queries search code columns rather than descriptions, preventing a value such as `2` from matching unrelated description text.

### Drug / NDC dataset

Required columns:

```text
NDC
PROPRIETARYNAME
NONPROPRIETARYNAME
SUBSTANCENAME
```

Example:

```csv
NDC,PROPRIETARYNAME,NONPROPRIETARYNAME,SUBSTANCENAME
250,Example Brand,example generic,EXAMPLE INGREDIENT
```

The application searches the `NDC` identifier and the combined text of all three required name/substance columns. Numeric NDC values shorter than 11 digits are left-padded with zeros when the file loads. For example, `250` is displayed as `00000000250`. Already-11-digit identifiers and non-numeric identifiers are left unchanged. Both the original value and normalized 11-digit value can be used to search.

### File size and encoding

- Supported encodings are UTF-8 (including UTF-8 with BOM), Windows-1252, and Latin-1.
- The application expects comma-separated content. A tab- or semicolon-delimited file should be converted to CSV first.
- Very large parent files take longer to parse and search and require more RAM.

## 6. Managing parent and user-added data

### Read-only parent datasets

The three authoritative parent files remain in `data`. Users can view their record counts under **Manage datasets**, but the browser provides no upload or replace control. The server also rejects requests to the legacy `/upload` endpoint. Only an administrator with filesystem access can install or replace a parent dataset.

The server loads valid parent files automatically at startup:

- `data/diagnosis_codes.csv`
- `data/procedure_codes.csv`
- `data/lu_ndc(in).csv`

### Adding a separate user record

1. Open **Manage datasets**.
2. Locate Diagnosis, Procedure, or NDC.
3. Select **Add record**.
4. For diagnosis/procedure records, enter the required `codes` and `Description` values and any available metadata: `code_type`, `code_version`, `bill_type`, `cancer_type`, `cancer`, `net`, and `newly_identified`. For NDC records, enter `NDC`, at least one drug/name field, and any available NDC metadata.
5. Select **Save separate record**.

User additions never modify the parent files. They are appended to one of these quarantined CSV files:

- `uploads/diagnosis/user_records.csv`
- `uploads/procedure/user_records.csv`
- `uploads/ndc/user_records.csv`

The cards show parent and user-added counts separately. Searches include both sources, and the `Data_Source` result column identifies **Parent dataset** or **User-added**. Exact duplicate identifiers are rejected. Numeric user-added NDC values are normalized to 11 digits using the same rule as parent NDC values.

Diagnosis and procedure user CSV files use the same nine-column structure as the supplied parent datasets: `code_type`, `code_version`, `codes`, `Description`, `bill_type`, `cancer_type`, `cancer`, `net`, and `newly_identified`. Only `codes` and `Description` are mandatory in the form; optional fields are saved as blank cells when omitted.

NDC user CSV files use the same 13-column structure as the supplied parent dataset: `NDC`, `PHARM_CLASSES`, `PROPRIETARYNAME`, `NONPROPRIETARYNAME`, `SUBSTANCENAME`, `GENERID`, `GENIND`, `DOSAGEFORMNAME`, `ACTIVE_NUMERATOR_STRENGTH`, `STRNGTH`, `ACTIVE_INGRED_UNIT`, `usc`, and `usc_desc`. `NDC` and at least one of the three name/substance fields are required; other values may be blank.

Separating user additions protects the parent files but does not prove that an addition is correct. An authorized reviewer should inspect the user CSV files before promoting any record into an authoritative dataset.

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
- Diagnosis and procedure searches inspect `Description` and, when present, a `code` or `codes` column.
- Diagnosis/procedure codes of three or more characters use case-insensitive prefix matching. Shorter code inputs use exact matching.
- Drug/NDC searches inspect `NDC` plus the three combined name and substance fields.
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
- Confirm that diagnosis/procedure identifiers are in a column named `code` or `codes` (capitalization does not matter), and that drug identifiers are in the required `NDC` column.

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

1. The entered query is compared with `Short_Term`, `Long_Term`, and every semicolon-separated related name using an exact, case-insensitive comparison.
2. When a row matches, each semicolon-separated value in `Search_Terms` is searched.
3. The short and long terms are also added to the search, with duplicates removed.
4. If there is no exact match, the original query is used unchanged.

Blank or malformed terminology files are ignored. Expansion may increase the result count because a row is returned when any expanded term matches. The `/abbreviations/<term>` endpoint can be used to inspect the resolved options, while the normal `/search` request applies expansion automatically.

### Teaching the application an unknown term

When a search is not already recognized in `medical_terms.csv`, the results page displays **Teach MedCode Finder this medical term**:

1. Select **Add terminology**.
2. Enter the short term or abbreviation, if one exists.
3. Enter the full medical term.
4. Enter other names or synonyms separated by semicolons.
5. Select **Save terminology**.

The relationship is appended to the local `data/medical_terms.csv` file, and the current search runs again with all related terms. Later searches using the short term, full term, or any saved synonym resolve to the same group. The application rejects a value that already belongs to another terminology row to avoid ambiguous mappings.

Review user-added terminology before relying on it. The application stores the relationship supplied by the user but does not medically validate abbreviations, spellings, synonyms, or equivalence.

## 9. Understanding results

The results area contains:

- The query and, when applicable, the terms used after expansion
- A summary card with the total match count for each searched dataset
- A table containing dataset columns plus `Data_Source`
- A truncation notice when more than 500 rows matched

Empty CSV cells appear as blank cells in the browser. Parent results appear before user-added results; the application does not sort by relevance.

## 10. Data storage, privacy, and security

- Administrator-managed parent datasets are stored in `data`; user additions are stored in `uploads`.
- Search requests are processed by the local Flask server.
- The application code does not send datasets or queries to an external API.
- Data remains on disk after the server stops and is reloaded on the next start.
- Anyone with access to the computer and project directory may be able to read the parent and user-added CSV files.

Do not load protected health information or other sensitive data unless the computer, user accounts, storage, backups, and operating procedures meet your organization's requirements. This application does not provide user authentication, encryption at rest, an audit trail, role-based permissions, or automatic retention/deletion controls.

Only an administrator should remove or replace a parent dataset. Stop the server, manage only its corresponding file in `data`, and then restart:

- `diagnosis_codes.csv`
- `procedure_codes.csv`
- `lu_ndc(in).csv`

Keep the `.gitkeep` files; they preserve empty data/upload directories in source control. Parent and user-record CSV files are excluded by `.gitignore`, but you should still verify staged files before committing.

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

Open the CSV and compare its header row with the required column names. Remove leading/trailing spaces and preserve capitalization. For NDC data, `NDC` and all three name/substance columns must exist even if some cells are blank.

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

Parent files are loaded into memory when the server starts. User additions are loaded immediately after the form saves them. If any CSV was edited directly on disk, restart the server to reload it.

### Dataset manager immediately reopens

This is expected when any of the three dataset types is missing or invalid. You can close the panel and search only the loaded datasets.

## 12. Backup and updates

To back up the application configuration and data, stop the server and copy the project folder to an approved secure location. Treat copies of the `data` directory according to the sensitivity of the underlying datasets.

When replacing a code set:

1. Obtain the new dataset from an authoritative source.
2. Confirm that the required columns are present.
3. Keep a backup if your retention policy requires it.
4. Replace the appropriate parent file in `data` while the server is stopped.
5. Restart the server, confirm the reported parent row count, and run several known searches.
6. Review the corresponding `uploads` CSV before merging any approved additions.
7. Record the dataset version and effective date outside the application; MedCode Finder does not track them automatically.

## 13. Technical reference

### Project layout

```text
app.py                         Flask server, loading, validation, and search
requirements.txt              Python dependencies
templates/index.html          Browser page structure
static/css/style.css          Interface styling
static/js/app.js              Record addition, search, and result interactions
data/                          Locally stored CSV files
uploads/                       Separate user-added CSV records by dataset type
scripts/import_abbreviations.py  Legacy/helper catalog-import script
docs/USER_MANUAL.md           This manual
```

### Local HTTP endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/` | Display the application |
| `GET` | `/status` | Return dataset availability, row counts, and load errors |
| `GET` | `/abbreviations/<term>` | Show terminology resolution for a term |
| `POST` | `/medical-terms` | Validate and save a user-added terminology relationship |
| `POST` | `/upload` | Reject parent replacement attempts (`403`) |
| `POST` | `/records` | Validate and save a separate user-added record |
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
- It does not search every displayed column; diagnosis/procedure search is limited to `Description` and optional `code`/`codes` columns, while NDC search uses `NDC` and the three configured name/substance columns.
- It does not provide fuzzy search, relevance ranking, filters, pagination, or export.
- It displays at most 500 rows per dataset per search.
- It is designed for one local user and has no multi-user concurrency or access-control model.
- Terminology expansion relies entirely on the optional local mapping file.

These limitations should be considered before adapting the application to a production or regulated workflow.
