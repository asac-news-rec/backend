import psycopg
from psycopg.rows import dict_row

from . import config

def connect():
    return psycopg.connect(
        host = config.PGHOST,
        port = config.PGPORT,
        dbname = config.PGDATABASE,
        user = config.PGUSER,
        password = config.PGPASSWORD,
        row_factory = dict_row,
        connect_timeout = 5,
        options = "-c statement_timeout=10000 -c lock_timeout=5000"
    )