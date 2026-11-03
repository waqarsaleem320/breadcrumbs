"""Shared Meta API settings."""
from pathlib import Path

BASE_URL = "https://api.meta.ai/v1"
SPARK_MODEL = "muse-spark-1.3"
SAM_MODEL = "sam-3.1"
ROOT = Path(__file__).resolve().parent.parent


def load_key() -> str:
    """Return MODEL_API_KEY from the project .env file."""
    env = ROOT / ".env"
    if not env.exists():
        raise RuntimeError("No .env file: add MODEL_API_KEY=... to run live checks. The sample works without it.")
    for line in env.read_text(encoding="utf-8-sig", errors="replace").replace("\x00", "").splitlines():
        if line.startswith("MODEL_API_KEY="):
            return line.split("=", 1)[1].strip().strip("\"'")
    raise RuntimeError("MODEL_API_KEY missing from .env")
