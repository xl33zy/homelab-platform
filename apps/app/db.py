import os

from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool


def create_pool() -> ConnectionPool:
    return ConnectionPool(
        conninfo="",
        min_size=int(os.environ.get("DB_POOL_MIN", "1")),
        max_size=int(os.environ.get("DB_POOL_MAX", "10")),
        timeout=5,
        kwargs={"row_factory": dict_row, "connect_timeout": 5},
        open=False,
    )
