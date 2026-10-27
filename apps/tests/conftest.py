import pathlib

import psycopg
import pytest
from fastapi.testclient import TestClient

INIT_SQL = pathlib.Path(__file__).resolve().parent.parent / "init.sql"


@pytest.fixture(scope="session", autouse=True)
def schema():
    try:
        with psycopg.connect(autocommit=True, connect_timeout=5) as conn:
            conn.execute(INIT_SQL.read_text())
    except psycopg.OperationalError as exc:
        pytest.exit(f"PostgreSQL недоступен (проверь переменные PG*): {exc}", returncode=2)


@pytest.fixture(autouse=True)
def clean_table():
    with psycopg.connect(autocommit=True) as conn:
        conn.execute("TRUNCATE notes RESTART IDENTITY")


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
