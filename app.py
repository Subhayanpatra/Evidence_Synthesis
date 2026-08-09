from pathlib import Path
from threading import Lock
import re

import pandas as pd
from flask import Flask, jsonify, render_template, request
from werkzeug.utils import secure_filename


BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)
MEDICAL_TERMS_FILE = DATA_DIR / "medical_terms.csv"
MEDICAL_TERM_COLUMNS = ["Text", "Short_Term", "Long_Term", "Search_Terms"]

FILES = {
    "diagnosis": "diagnosis_codes.csv",
    "procedure": "procedure_codes.csv",
    "ndc": "lu_ndc(in).csv",
}

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 250 * 1024 * 1024

frames = {key: None for key in FILES}
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


def load_dataset(kind):
    path = DATA_DIR / FILES[kind]
    if not path.exists():
        frames[kind] = None
        load_errors.pop(kind, None)
        return

    try:
        df = read_csv_compatible(path)
        if kind in ("diagnosis", "procedure"):
            if "Description" not in df.columns:
                raise ValueError("Required column 'Description' was not found.")
        else:
            required = {"NDC", "PROPRIETARYNAME", "NONPROPRIETARYNAME", "SUBSTANCENAME"}
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

        frames[kind] = df
        load_errors.pop(kind, None)
    except Exception as exc:
        frames[kind] = None
        load_errors[kind] = str(exc)


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
            "error": load_errors.get(kind),
        }
    return status


reload_all()


@app.get("/")
def home():
    return render_template("index.html")


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
    kind = request.form.get("kind", "")
    uploaded = request.files.get("file")

    if kind not in FILES:
        return jsonify({"error": "Invalid dataset type."}), 400
    if not uploaded or not uploaded.filename:
        return jsonify({"error": "Choose a CSV file first."}), 400
    if Path(secure_filename(uploaded.filename)).suffix.lower() != ".csv":
        return jsonify({"error": "Only CSV files are accepted."}), 400

    target = DATA_DIR / FILES[kind]
    uploaded.save(target)
    with data_lock:
        load_dataset(kind)

    if load_errors.get(kind):
        target.unlink(missing_ok=True)
        error = load_errors[kind]
        load_dataset(kind)
        return jsonify({"error": error}), 400

    return jsonify({"message": "Dataset loaded successfully.", "status": dataset_status()[kind]})


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
            else:
                # Description is required. Common singular/plural code column
                # names are detected without requiring specific capitalization.
                search_columns = ["Description"]
                search_columns.extend(
                    column for column in df.columns
                    if column.casefold() in {"code", "codes"}
                )
                searchable = df[search_columns].fillna("").astype(str).agg(" ".join, axis=1)
            mask = pd.Series(False, index=df.index)
            for term in search_terms:
                mask |= searchable.str.contains(
                    term_pattern(term), case=False, na=False, regex=True
                )
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
    app.run(debug=True, host="127.0.0.1", port=5000)
