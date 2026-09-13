from pathlib import Path
from threading import Lock
from io import BytesIO
import re

import pandas as pd
from flask import Flask, jsonify, render_template, request


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
USER_UPLOAD_DIR = BASE_DIR / "uploads"
for upload_kind in ("diagnosis", "procedure", "ndc"):
    (USER_UPLOAD_DIR / upload_kind).mkdir(parents=True, exist_ok=True)
MEDICAL_TERMS_FILE = DATA_DIR / "medical_terms.csv"
MEDICAL_TERM_COLUMNS = ["Text", "Short_Term", "Long_Term", "Search_Terms"]

FILES = {
    "diagnosis": "diagnosis_codes.csv",
    "procedure": "procedure_codes.csv",
    "ndc": "lu_ndc(in).csv",
}
USER_RECORD_FILES = {
    kind: USER_UPLOAD_DIR / kind / "user_records.csv" for kind in FILES
}
USER_RECORD_COLUMNS = {
    "diagnosis": [
        "code_type", "code_version", "codes", "Description", "bill_type",
        "cancer_type", "cancer", "net", "newly_identified",
    ],
    "procedure": [
        "code_type", "code_version", "codes", "Description", "bill_type",
        "cancer_type", "cancer", "net", "newly_identified",
    ],
    "ndc": [
        "NDC", "PHARM_CLASSES", "PROPRIETARYNAME", "NONPROPRIETARYNAME",
        "SUBSTANCENAME", "GENERID", "GENIND", "DOSAGEFORMNAME",
        "ACTIVE_NUMERATOR_STRENGTH", "STRNGTH", "ACTIVE_INGRED_UNIT",
        "usc", "usc_desc",
    ],
}
NDC_REQUIRED_COLUMNS = {"NDC", "PROPRIETARYNAME", "NONPROPRIETARYNAME", "SUBSTANCENAME"}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024

frames = {key: None for key in FILES}
base_counts = {key: 0 for key in FILES}
user_counts = {key: 0 for key in FILES}
load_errors = {}
data_lock = Lock()


def read_csv_compatible(path):
    """Read CSV exports encoded as UTF-8 or common Windows/Latin encodings."""
    last_error = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            # Codes are identifiers, not numbers. Reading all fields as text keeps
            # significant leading zeroes intact and makes code searches reliable.
            return pd.read_csv(path, low_memory=False, encoding=encoding, dtype=str)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise last_error


def read_uploaded_csv(uploaded):
    """Read an uploaded CSV using the same supported encodings as parent files."""
    content = uploaded.read()
    last_error = None
    for encoding in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            return pd.read_csv(BytesIO(content), low_memory=False, encoding=encoding, dtype=str)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise last_error


def load_medical_terms():
    """Load the local terminology table used to expand recognized searches."""
    try:
        terms = pd.read_csv(MEDICAL_TERMS_FILE, dtype=str).fillna("")
        required = set(MEDICAL_TERM_COLUMNS)
        if not required.issubset(terms.columns):
            return []
        return terms.to_dict(orient="records")
    except (OSError, ValueError, TypeError, pd.errors.ParserError):
        return []


def resolve_search_terms(keyword):
    """Expand an exact short, long, or synonym match; otherwise use the input."""
    normalized = keyword.casefold()
    for row in load_medical_terms():
        aliases = [value.strip() for value in row["Search_Terms"].split(";") if value.strip()]
        candidates = [row["Short_Term"].strip(), row["Long_Term"].strip(), *aliases]
        if any(value.casefold() == normalized for value in candidates if value):
            expanded = aliases + [row["Short_Term"].strip(), row["Long_Term"].strip()]
            return list(dict.fromkeys(value for value in expanded if value))
    return [keyword]


def split_term_aliases(value):
    """Accept semicolon/newline-separated aliases and return unique clean values."""
    aliases = []
    seen = set()
    for item in re.split(r"[;\r\n]+", str(value)):
        cleaned = item.strip()
        if cleaned and cleaned.casefold() not in seen:
            aliases.append(cleaned)
            seen.add(cleaned.casefold())
    return aliases


def save_medical_term(short_term, long_term, aliases):
    """Append one validated terminology relationship to the local CSV catalog."""
    if MEDICAL_TERMS_FILE.exists():
        existing_columns = set(pd.read_csv(MEDICAL_TERMS_FILE, nrows=0).columns)
        if not set(MEDICAL_TERM_COLUMNS).issubset(existing_columns):
            raise ValueError(
                "The existing medical_terms.csv is missing required columns; "
                "correct it before adding terms."
            )
    rows = load_medical_terms()
    normalized_new = {value.casefold() for value in [short_term, long_term, *aliases] if value}

    for row in rows:
        existing = [row["Short_Term"].strip(), row["Long_Term"].strip()]
        existing.extend(split_term_aliases(row["Search_Terms"]))
        duplicate = next((value for value in existing if value.casefold() in normalized_new), None)
        if duplicate:
            raise ValueError(f"'{duplicate}' already belongs to an existing medical term.")

    primary = {short_term.casefold(), long_term.casefold()}
    aliases = [value for value in aliases if value.casefold() not in primary]
    rows.append({
        "Text": long_term,
        "Short_Term": short_term,
        "Long_Term": long_term,
        "Search_Terms": ";".join(aliases),
    })
    temporary_file = MEDICAL_TERMS_FILE.with_suffix(".tmp")
    pd.DataFrame(rows, columns=MEDICAL_TERM_COLUMNS).to_csv(
        temporary_file, index=False, encoding="utf-8-sig"
    )
    temporary_file.replace(MEDICAL_TERMS_FILE)


def term_pattern(term):
    """Match a literal term without allowing it inside a larger word."""
    return rf"(?<!\w){re.escape(term)}(?!\w)"


def clean_records(df):
    """Convert NaN values to JSON-safe nulls."""
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


def normalize_ndc(value):
    """Left-pad numeric NDC identifiers to 11 digits without altering other values."""
    if pd.isna(value):
        return value
    cleaned = str(value).strip()
    if cleaned.isdigit() and len(cleaned) < 11:
        return cleaned.zfill(11)
    return cleaned


def code_prefix_mask(series, term):
    """Match complete short codes or prefixes containing at least three characters."""
    normalized_codes = series.fillna("").astype(str).str.strip().str.casefold()
    normalized_term = term.strip().casefold()
    if len(normalized_term) < 3:
        return normalized_codes.eq(normalized_term)
    return normalized_codes.str.startswith(normalized_term, na=False)


def prepare_dataset(kind, df, source):
    """Validate and prepare one parent or user-added dataframe for searching."""
    df = df.copy()
    if kind in ("diagnosis", "procedure"):
        if "Description" not in df.columns:
            raise ValueError("Required column 'Description' was not found.")
        if not any(column.casefold() in {"code", "codes"} for column in df.columns):
            raise ValueError("Required code column 'code' or 'codes' was not found.")
    else:
        required = NDC_REQUIRED_COLUMNS
        missing = sorted(required.difference(df.columns))
        if missing:
            raise ValueError("Missing required columns: " + ", ".join(missing))
        original_ndc = df["NDC"].fillna("").astype(str).str.strip()
        df["NDC"] = df["NDC"].map(normalize_ndc)
        df["content"] = (
            df["NDC"].fillna("").astype(str) + " "
            + original_ndc + " "
            + df["PROPRIETARYNAME"].fillna("").astype(str) + " "
            + df["NONPROPRIETARYNAME"].fillna("").astype(str) + " "
            + df["SUBSTANCENAME"].fillna("").astype(str)
        )
    df["Data_Source"] = source
    return df


def load_dataset(kind):
    """Load the read-only parent dataset and separately stored user additions."""
    parent_path = DATA_DIR / FILES[kind]
    user_path = USER_RECORD_FILES[kind]
    datasets = []
    base_counts[kind] = 0
    user_counts[kind] = 0

    try:
        if parent_path.exists():
            parent = prepare_dataset(kind, read_csv_compatible(parent_path), "Parent dataset")
            base_counts[kind] = len(parent)
            datasets.append(parent)
        if user_path.exists():
            additions = prepare_dataset(kind, read_csv_compatible(user_path), "User-added")
            user_counts[kind] = len(additions)
            datasets.append(additions)

        frames[kind] = pd.concat(datasets, ignore_index=True, sort=False) if datasets else None
        load_errors.pop(kind, None)
    except Exception as exc:
        frames[kind] = None
        load_errors[kind] = str(exc)


def save_user_records(kind, records):
    """Append validated records to a user CSV without changing parent data."""
    target = USER_RECORD_FILES[kind]
    columns = USER_RECORD_COLUMNS[kind]
    existing = read_csv_compatible(target) if target.exists() else pd.DataFrame(columns=columns)
    required = {"codes", "Description"} if kind in ("diagnosis", "procedure") else NDC_REQUIRED_COLUMNS
    if not required.issubset(existing.columns):
        raise ValueError(f"The existing {target.name} has invalid columns.")
    for column in columns:
        if column not in existing.columns:
            existing[column] = ""
    updated = pd.concat([existing[columns], pd.DataFrame(records, columns=columns)], ignore_index=True)
    temporary_file = target.with_suffix(".tmp")
    updated.to_csv(temporary_file, index=False, encoding="utf-8-sig")
    temporary_file.replace(target)


def record_exists(kind, identifier):
    """Check an exact code/NDC against parent and user-added records."""
    df = frames[kind]
    if df is None:
        return False
    if kind == "ndc":
        return df["NDC"].fillna("").astype(str).str.casefold().eq(identifier.casefold()).any()
    for column in df.columns:
        if column.casefold() in {"code", "codes"}:
            if df[column].fillna("").astype(str).str.strip().str.casefold().eq(identifier.casefold()).any():
                return True
    return False


def existing_identifiers(kind):
    """Return normalized identifiers from parent and user-added records."""
    df = frames[kind]
    if df is None:
        return set()
    if kind == "ndc":
        return set(df["NDC"].fillna("").astype(str).str.strip().str.casefold()) - {""}
    identifiers = set()
    for column in df.columns:
        if column.casefold() in {"code", "codes"}:
            identifiers.update(df[column].fillna("").astype(str).str.strip().str.casefold())
    identifiers.discard("")
    return identifiers


def reload_all():
    with data_lock:
        for kind in FILES:
            load_dataset(kind)


def dataset_status():
    status = {}
    for kind, filename in FILES.items():
        df = frames[kind]
        status[kind] = {
            "filename": filename,
            "loaded": df is not None,
            "rows": 0 if df is None else len(df),
            "base_loaded": (DATA_DIR / filename).exists() and not bool(load_errors.get(kind)),
            "base_rows": base_counts[kind],
            "user_rows": user_counts[kind],
            "error": load_errors.get(kind),
        }
    return status


reload_all()


@app.get("/")
def home():
    # In the unified server this Flask app is mounted at /code-lookup, so its
    # own root is the Intelligent Code Lookup workspace.
    return render_template("index.html")


@app.get("/code-lookup")
def code_lookup():
    return render_template("index.html")


@app.get("/evidence-synthesis")
def evidence_synthesis():
    return render_template("evidence_synthesis.html")


@app.get("/status")
def status():
    return jsonify(dataset_status())


@app.get("/abbreviations/<term>")
def abbreviation_options(term):
    keyword = term.strip()
    options = resolve_search_terms(keyword)
    return jsonify({"term": keyword, "matched": options != [keyword], "options": options})


@app.post("/medical-terms")
def add_medical_term():
    payload = request.get_json(silent=True) or {}
    short_term = str(payload.get("short_term", "")).strip()
    long_term = str(payload.get("long_term", "")).strip()
    aliases = split_term_aliases(payload.get("search_terms", ""))

    if not long_term:
        return jsonify({"error": "Enter the full medical term."}), 400
    if not short_term and not aliases:
        return jsonify({"error": "Enter an abbreviation or at least one related search term."}), 400
    if any(len(value) > 300 for value in [short_term, long_term, *aliases]):
        return jsonify({"error": "Each terminology value must be 300 characters or fewer."}), 400
    if len(aliases) > 50:
        return jsonify({"error": "Enter no more than 50 related search terms."}), 400

    try:
        with data_lock:
            save_medical_term(short_term, long_term, aliases)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except (OSError, TypeError, pd.errors.ParserError) as exc:
        return jsonify({"error": f"Could not save the medical term: {exc}"}), 500

    return jsonify({
        "message": "Medical terminology saved locally.",
        "short_term": short_term,
        "long_term": long_term,
        "search_terms": resolve_search_terms(short_term or long_term),
    }), 201


@app.post("/upload")
def upload():
    return jsonify({
        "error": "Parent datasets are read-only and cannot be replaced by users."
    }), 403


@app.post("/records")
def add_record():
    payload = request.get_json(silent=True) or {}
    kind = str(payload.get("kind", "")).strip().lower()
    if kind not in FILES:
        return jsonify({"error": "Invalid dataset type."}), 400

    if kind in ("diagnosis", "procedure"):
        code = str(payload.get("code", "")).strip()
        description = str(payload.get("description", "")).strip()
        if not code or not description:
            return jsonify({"error": "Enter both the code and description."}), 400
        record = {
            "code_type": str(payload.get("code_type", "")).strip(),
            "code_version": str(payload.get("code_version", "")).strip(),
            "codes": code,
            "Description": description,
            "bill_type": str(payload.get("bill_type", "")).strip(),
            "cancer_type": str(payload.get("cancer_type", "")).strip(),
            "cancer": str(payload.get("cancer", "")).strip(),
            "net": str(payload.get("net", "")).strip(),
            "newly_identified": str(payload.get("newly_identified", "")).strip(),
        }
        identifier = code
    else:
        ndc = normalize_ndc(str(payload.get("ndc", "")).strip())
        proprietary = str(payload.get("proprietary_name", "")).strip()
        nonproprietary = str(payload.get("nonproprietary_name", "")).strip()
        substance = str(payload.get("substance_name", "")).strip()
        if not ndc:
            return jsonify({"error": "Enter the NDC code."}), 400
        if not any((proprietary, nonproprietary, substance)):
            return jsonify({"error": "Enter at least one drug or substance name."}), 400
        record = {
            "NDC": ndc,
            "PHARM_CLASSES": str(payload.get("pharm_classes", "")).strip(),
            "PROPRIETARYNAME": proprietary,
            "NONPROPRIETARYNAME": nonproprietary,
            "SUBSTANCENAME": substance,
            "GENERID": str(payload.get("generid", "")).strip(),
            "GENIND": str(payload.get("genind", "")).strip(),
            "DOSAGEFORMNAME": str(payload.get("dosage_form_name", "")).strip(),
            "ACTIVE_NUMERATOR_STRENGTH": str(payload.get("active_numerator_strength", "")).strip(),
            "STRNGTH": str(payload.get("strength", "")).strip(),
            "ACTIVE_INGRED_UNIT": str(payload.get("active_ingredient_unit", "")).strip(),
            "usc": str(payload.get("usc", "")).strip(),
            "usc_desc": str(payload.get("usc_desc", "")).strip(),
        }
        identifier = ndc

    if any(len(str(value)) > 500 for value in record.values()):
        return jsonify({"error": "Each field must be 500 characters or fewer."}), 400

    try:
        with data_lock:
            if record_exists(kind, identifier):
                return jsonify({"error": f"Code '{identifier}' already exists."}), 409
            save_user_records(kind, [record])
            load_dataset(kind)
            if load_errors.get(kind):
                raise ValueError(load_errors[kind])
    except (OSError, ValueError, TypeError, pd.errors.ParserError) as exc:
        return jsonify({"error": f"Could not save the record: {exc}"}), 500

    return jsonify({
        "message": "Record saved separately from the parent dataset.",
        "status": dataset_status()[kind],
    }), 201


@app.post("/records/import")
def import_records():
    kind = str(request.form.get("kind", "")).strip().lower()
    uploaded = request.files.get("file")
    if kind not in FILES:
        return jsonify({"error": "Invalid dataset type."}), 400
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Choose a CSV file first."}), 400
    if Path(uploaded.filename).suffix.lower() != ".csv":
        return jsonify({"error": "Only CSV files are accepted."}), 400

    try:
        incoming = read_uploaded_csv(uploaded).fillna("")
    except (UnicodeDecodeError, ValueError, TypeError, pd.errors.ParserError) as exc:
        return jsonify({"error": f"Could not read the CSV: {exc}"}), 400

    expected = USER_RECORD_COLUMNS[kind]
    missing = [column for column in expected if column not in incoming.columns]
    unexpected = [column for column in incoming.columns if column not in expected]
    if missing or unexpected:
        details = []
        if missing:
            details.append("Missing columns: " + ", ".join(missing))
        if unexpected:
            details.append("Unexpected columns: " + ", ".join(unexpected))
        return jsonify({
            "error": ". ".join(details) + ".",
            "expected_columns": expected,
            "missing_columns": missing,
            "unexpected_columns": unexpected,
        }), 400
    if incoming.empty:
        return jsonify({"error": "The CSV contains no records."}), 400

    incoming = incoming[expected].astype(str).apply(lambda column: column.str.strip())
    if kind in ("diagnosis", "procedure"):
        invalid = incoming.index[
            incoming["codes"].eq("") | incoming["Description"].eq("")
        ].tolist()
        identifiers = incoming["codes"]
    else:
        incoming["NDC"] = incoming["NDC"].map(normalize_ndc)
        missing_names = incoming[[
            "PROPRIETARYNAME", "NONPROPRIETARYNAME", "SUBSTANCENAME"
        ]].eq("").all(axis=1)
        invalid = incoming.index[incoming["NDC"].eq("") | missing_names].tolist()
        identifiers = incoming["NDC"]

    if invalid:
        rows = ", ".join(str(index + 2) for index in invalid[:10])
        suffix = " (first 10 shown)" if len(invalid) > 10 else ""
        return jsonify({
            "error": f"Required values are missing on CSV row(s): {rows}{suffix}."
        }), 400
    too_long = incoming.apply(lambda column: column.str.len().gt(500)).any(axis=1)
    if too_long.any():
        rows = ", ".join(str(index + 2) for index in incoming.index[too_long][:10])
        return jsonify({"error": f"Values exceed 500 characters on CSV row(s): {rows}."}), 400

    normalized = identifiers.str.casefold()
    duplicate_in_file = normalized[normalized.duplicated(keep=False)].unique().tolist()
    existing = existing_identifiers(kind)
    duplicate_existing = sorted(set(normalized).intersection(existing))
    duplicates = duplicate_in_file + [value for value in duplicate_existing if value not in duplicate_in_file]
    if duplicates:
        shown = ", ".join(duplicates[:10])
        suffix = " (first 10 shown)" if len(duplicates) > 10 else ""
        return jsonify({"error": f"Duplicate code(s): {shown}{suffix}."}), 409

    try:
        with data_lock:
            # Recheck after acquiring the lock in case another request added data.
            conflicts = sorted(set(normalized).intersection(existing_identifiers(kind)))
            if conflicts:
                return jsonify({"error": f"Duplicate code(s): {', '.join(conflicts[:10])}."}), 409
            save_user_records(kind, incoming.to_dict(orient="records"))
            load_dataset(kind)
            if load_errors.get(kind):
                raise ValueError(load_errors[kind])
    except (OSError, ValueError, TypeError, pd.errors.ParserError) as exc:
        return jsonify({"error": f"Could not import the records: {exc}"}), 500

    return jsonify({
        "message": f"{len(incoming):,} record(s) imported into separate user storage.",
        "imported": len(incoming),
        "status": dataset_status()[kind],
    }), 201


@app.post("/search")
def search():
    payload = request.get_json(silent=True) or {}
    keyword = str(payload.get("keyword", "")).strip()
    selected = payload.get("datasets", [])

    if not keyword:
        return jsonify({"error": "Enter a disease, procedure, drug name, or code."}), 400
    if not isinstance(selected, list) or not selected:
        return jsonify({"error": "Select at least one dataset."}), 400

    invalid = [item for item in selected if item not in FILES]
    if invalid:
        return jsonify({"error": "Invalid dataset selection."}), 400

    results = {}
    summary = []
    unavailable = []
    search_terms = resolve_search_terms(keyword)

    with data_lock:
        for kind in selected:
            df = frames[kind]
            if df is None:
                unavailable.append(kind)
                continue

            if kind == "ndc":
                searchable = df["content"].fillna("").astype(str)
                mask = pd.Series(False, index=df.index)
                for term in search_terms:
                    mask |= searchable.str.contains(
                        term_pattern(term), case=False, na=False, regex=True
                    )
            else:
                # Description is required. Common singular/plural code column
                # names are detected without requiring specific capitalization.
                code_columns = [
                    column for column in df.columns
                    if column.casefold() in {"code", "codes"}
                ]
                descriptions = df["Description"].fillna("").astype(str)
                mask = pd.Series(False, index=df.index)
                for term in search_terms:
                    # A digits-only query is a medical code lookup; excluding
                    # descriptions avoids unrelated matches for values like "2".
                    if not term.strip().isdigit():
                        mask |= descriptions.str.contains(
                            term_pattern(term), case=False, na=False, regex=True
                        )
                    for column in code_columns:
                        mask |= code_prefix_mask(df[column], term)
            matched = df.loc[mask].drop(columns=["content"], errors="ignore")
            total = len(matched)
            # Keep the response/browser responsive for very broad searches.
            shown = matched.head(500)
            results[kind] = {
                "total": total,
                "columns": shown.columns.tolist(),
                "rows": clean_records(shown),
                "truncated": total > len(shown),
            }
            summary.append({"dataset": kind, "matches": total})

    return jsonify({
        "keyword": keyword,
        "search_terms": search_terms,
        "expanded": search_terms != [keyword],
        "summary": summary,
        "results": results,
        "unavailable": unavailable,
    })


if __name__ == "__main__":
    # Keep the familiar `python app.py` command, but launch the unified Hub
    # instead of opening the Code Lookup application as the site's first page.
    import os
    import sys
    from pathlib import Path
    import uvicorn

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from server import app as hub_app

    uvicorn.run(
        hub_app,
        host=os.getenv("MEDEVIDENCE_HOST", "127.0.0.1"),
        port=int(os.getenv("MEDEVIDENCE_PORT", "5000")),
        reload=False,
    )
