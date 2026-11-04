from dotenv import load_dotenv
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env",override=False)

PGHOST      = os.environ.get("PGHOST","127.0.0l.1")
PGPORT      = os.environ.get("PGPORT","5433")
PGDATABASE  = os.environ.get("PGDATABASE","newsdb")
PGUSER      = os.environ.get("PGUSER","recommend")
PGPASSWORD  = os.environ.get("PGPASSWORD")