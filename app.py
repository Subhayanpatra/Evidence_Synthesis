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
            return pd.read_csv(path, low_memory=False, encoding=encoding)
        except UnicodeDecodeError as exc:
            last_error = exc
    raise last_error


def load_medical_terms():
    """Load the local terminology table used to expand recognized searches."""
    try:
        terms = pd.read_csv(MEDICAL_TERMS_FILE, dtype=str).fillna("")
        required = {"Text", "Short_Term", "Long_Term", "Search_Terms"}
        if not required.issubset(terms.columns):
            return []
        return terms.to_dict(orient="records")
    except (OSError, ValueError, TypeError, pd.errors.ParserError):
        return []


def resolve_search_terms(keyword):
    """Expand an exact short/long-term match; otherwise use the input directly."""
    normalized = keyword.casefold()
    for row in load_medical_terms():
        candidates = (row["Short_Term"].strip(), row["Long_Term"].strip())
        if any(value.casefold() == normalized for value in candidates if value):
            expanded = [value.strip() for value in row["Search_Terms"].split(";") if value.strip()]
            expanded.extend(value for value in candidates if value)
            return list(dict.fromkeys(expanded))
    return [keyword]


def term_pattern(term):
    """Match a literal term without allowing it inside a larger word."""
    return rf"(?<!\w){re.escape(term)}(?!\w)"


def clean_records(df):
    """Convert NaN values to JSON-safe nulls."""
    return df.astype(object).where(pd.notna(df), None).to_dict(orient="records")


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
            required = {"PROPRIETARYNAME", "NONPROPRIETARYNAME", "SUBSTANCENAME"}
            missing = sorted(required.difference(df.columns))
            if missing:
                raise ValueError("Missing required columns: " + ", ".join(missing))
            df["content"] = (
                df["PROPRIETARYNAME"].fillna("").astype(str) + " "
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

            column = "content" if kind == "ndc" else "Description"
            searchable = df[column].fillna("").astype(str)
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
