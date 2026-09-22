"""Application configuration. No paid APIs or API keys required."""
import os
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = Path(os.environ.get("OPERON_DATA_DIR", BACKEND_ROOT / "data"))
UPLOADS_DIR = DATA_DIR / "uploads"
MODELS_DIR = DATA_DIR / "models"
SYNTHETIC_DIR = DATA_DIR / "synthetic"
DUCKDB_PATH = Path(os.environ.get("OPERON_DB_PATH", DATA_DIR / "operon.duckdb"))

for d in (DATA_DIR, UPLOADS_DIR, MODELS_DIR, SYNTHETIC_DIR):
    d.mkdir(parents=True, exist_ok=True)

# Max upload size (bytes) - 500MB default, generous for large CSV exports.
MAX_UPLOAD_BYTES = int(os.environ.get("OPERON_MAX_UPLOAD_BYTES", 500 * 1024 * 1024))

# CORS origins for the Next.js dev/prod client.
CORS_ORIGINS = os.environ.get(
    "OPERON_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"
).split(",")

DEFAULT_CURRENCY = "USD"
