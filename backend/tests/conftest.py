"""Imposta un ambiente di test isolato PRIMA di importare l'app (SQLite, niente Redis, niente LLM)."""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
_db = ROOT / "test_biopulse.db"
if _db.exists():
    _db.unlink()
os.environ["DATABASE_URL"] = f"sqlite:///{_db}"
os.environ["REDIS_URL"] = ""
os.environ["GROQ_API_KEY"] = ""
os.environ["CLINICIAN_KEY"] = "demo-clinician"
os.environ["APP_ENV"] = "test"
os.environ["AUTH_DISABLED"] = "true"
