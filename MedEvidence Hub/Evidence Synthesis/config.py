import os
from pathlib import Path

from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().with_name(".env"))


def _legacy_secret(name: str, default: str = "") -> str:
    """Read the former Streamlit secret file without importing Streamlit."""
    try:
        import tomllib

        secret_path = Path(".streamlit") / "secrets.toml"
        if not secret_path.is_file():
            return default
        with secret_path.open("rb") as secret_file:
            secrets = tomllib.load(secret_file)
        return str(secrets.get(name, default))
    except (OSError, TypeError, ValueError):
        return default


EMAIL = os.getenv("NCBI_EMAIL") or _legacy_secret(
    "NCBI_EMAIL",
    "your_email@example.com",
)
NCBI_API_KEY = os.getenv("NCBI_API_KEY") or _legacy_secret("NCBI_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY") or _legacy_secret("OPENAI_API_KEY", "")
