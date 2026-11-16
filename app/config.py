from dotenv import load_dotenv
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env",override=False)

PGHOST      = os.environ.get("PGHOST","127.0.0.1")
PGPORT      = os.environ.get("PGPORT","5433")
PGDATABASE  = os.environ.get("PGDATABASE","newsdb")
PGUSER      = os.environ.get("PGUSER","recommend")
PGPASSWORD  = os.environ.get("PGPASSWORD")


def get_pool_max_size() -> int:
    try:
        size = int(os.environ.get("DB_POOL_MAX_SIZE", "4"))
    except ValueError as exc:
        raise ValueError("DB_POOL_MAX_SIZE must be a positive integer") from exc
    if size < 1:
        raise ValueError("DB_POOL_MAX_SIZE must be a positive integer")
    return size
