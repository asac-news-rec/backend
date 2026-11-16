from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config


_pool = None


@contextmanager
def database_pool():
    """FastAPI 프로세스에서 공유하는 풀을 시작하고 종료 시 닫습니다."""
    global _pool
    with ConnectionPool(
        kwargs={
            "host": config.PGHOST,
            "port": config.PGPORT,
            "dbname": config.PGDATABASE,
            "user": config.PGUSER,
            "password": config.PGPASSWORD,
            "row_factory": dict_row,
            "connect_timeout": 5,
            "options": "-c statement_timeout=10000 -c lock_timeout=5000",
        },
        min_size=0,
        max_size=config.get_pool_max_size(),
        timeout=3.0,
        check=ConnectionPool.check_connection,
        open=False,
    ) as pool:
        _pool = pool
        try:
            yield
        finally:
            _pool = None


def connect():
    if _pool is None:
        raise psycopg.OperationalError("Database connection pool is not running")
    return _pool.connection()
