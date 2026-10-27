import psycopg
import cleanup


def _insert(text: str, age_days: int) -> None:
    with psycopg.connect(autocommit=True) as conn:
        conn.execute(
            "INSERT INTO notes (text, created_at) VALUES (%s, now() - make_interval(days => %s))",
            (text, age_days),
        )


def _texts() -> list[str]:
    with psycopg.connect() as conn:
        return [r[0] for r in conn.execute("SELECT text FROM notes ORDER BY id")]


def test_cleanup_removes_only_old_notes(monkeypatch, capsys):
    _insert("old", 40)
    _insert("border-new", 29)
    _insert("fresh", 0)
    monkeypatch.setenv("NOTES_RETENTION_DAYS", "30")

    assert cleanup.main() == 0

    assert _texts() == ["border-new", "fresh"]
    assert "deleted=1" in capsys.readouterr().out


def test_cleanup_default_is_30_days(monkeypatch):
    monkeypatch.delenv("NOTES_RETENTION_DAYS", raising=False)
    _insert("old", 31)
    _insert("fresh", 1)
    assert cleanup.main() == 0
    assert _texts() == ["fresh"]


def test_cleanup_rejects_bad_retention(monkeypatch):
    _insert("old", 400)
    monkeypatch.setenv("NOTES_RETENTION_DAYS", "0")
    assert cleanup.main() == 2
    assert _texts() == ["old"]
