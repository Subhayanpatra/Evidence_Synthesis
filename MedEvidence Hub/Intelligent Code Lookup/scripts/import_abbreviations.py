"""Merge a Python-style abbreviation mapping into the app's JSON catalog."""

import ast
import json
import re
import sys
from pathlib import Path


ENTRY_PATTERN = re.compile(r'"([^"]+)"\s*:\s*(\[(?:.|\n)*?\])\s*,?', re.MULTILINE)


def repair_text(value):
    if "Ã" not in value:
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def main(source_name, target_name):
    source = Path(source_name).read_text(encoding="utf-8-sig")
    target = Path(target_name)
    catalog = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {}
    merged = {key.upper(): list(values) for key, values in catalog.items()}

    imported_entries = 0
    for match in ENTRY_PATTERN.finditer(source):
        key = match.group(1).strip().upper()
        values = ast.literal_eval(match.group(2))
        bucket = merged.setdefault(key, [])
        for value in values:
            cleaned = repair_text(str(value).strip())
            if cleaned and cleaned not in bucket:
                bucket.append(cleaned)
        imported_entries += 1

    target.write_text(
        json.dumps(dict(sorted(merged.items())), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Processed {imported_entries} entries into {len(merged)} unique abbreviations.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("Usage: import_abbreviations.py SOURCE TARGET")
    main(sys.argv[1], sys.argv[2])
