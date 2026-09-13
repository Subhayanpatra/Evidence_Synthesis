import json
import pathlib
import re


NOTEBOOK = pathlib.Path(r"C:\Users\HP\Downloads\Trial Model.ipynb")
SECRETS = pathlib.Path(r"C:\AI_extract\.env")


def main() -> None:
    notebook = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    source = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook.get("cells", [])
    )
    ncbi_match = re.search(r"Entrez\.api_key\s*=\s*[\"']([^\"']+)[\"']", source)
    openai_match = re.search(
        r"(?:OPENAI_API_KEY\s*=|OpenAI\(\s*api_key\s*=)\s*[\"']([^\"']+)[\"']",
        source,
    )

    if not ncbi_match and not openai_match:
        print("No API keys found")
        return

    SECRETS.parent.mkdir(exist_ok=True)
    current = SECRETS.read_text(encoding="utf-8") if SECRETS.exists() else ""
    lines = [
        line
        for line in current.splitlines()
        if not line.startswith("NCBI_API_KEY=") and not line.startswith("OPENAI_API_KEY=")
    ]
    if ncbi_match:
        lines.append(f"NCBI_API_KEY={ncbi_match.group(1)}")
    if openai_match:
        lines.append(f"OPENAI_API_KEY={openai_match.group(1)}")
    SECRETS.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("Environment file written")


if __name__ == "__main__":
    main()
