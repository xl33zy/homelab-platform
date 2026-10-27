from fastapi.testclient import TestClient


def test_create_and_get_note(client):
    created = client.post("/notes", json={"text": "первая заметка"})
    assert created.status_code == 201
    note = created.json()
    assert note["text"] == "первая заметка"
    assert note["id"] == 1
    assert note["created_at"]

    fetched = client.get(f"/notes/{note['id']}")
    assert fetched.status_code == 200
    assert fetched.json() == note


def test_text_is_stripped_and_validated(client):
    assert client.post("/notes", json={"text": "  hi  "}).json()["text"] == "hi"
    assert client.post("/notes", json={"text": "   "}).status_code == 422
    assert client.post("/notes", json={"text": ""}).status_code == 422
    assert client.post("/notes", json={"text": "x" * 1001}).status_code == 422
    assert client.post("/notes", json={}).status_code == 422


def test_get_missing_note_is_404(client):
    assert client.get("/notes/999").status_code == 404


def test_huge_id_is_422_not_500(client):
    assert client.get("/notes/99999999999999999999").status_code == 422


def test_list_is_newest_first_and_respects_limit(client):
    for i in range(5):
        client.post("/notes", json={"text": f"n{i}"})
    texts = [n["text"] for n in client.get("/notes").json()]
    assert texts == ["n4", "n3", "n2", "n1", "n0"]
    assert [n["text"] for n in client.get("/notes?limit=2").json()] == ["n4", "n3"]
    assert client.get("/notes?limit=0").status_code == 422
    assert client.get("/notes?limit=201").status_code == 422


def test_healthz_and_readyz(client):
    assert client.get("/healthz").json() == {"status": "ok"}
    assert client.get("/readyz").json() == {"status": "ready"}


def test_database_down(monkeypatch):
    """БД недоступна: процесс жив (healthz 200), но не готов (readyz 503), API отвечает 503."""
    from app.main import app

    monkeypatch.setenv("PGPORT", "1")  # на этом порту никто не слушает
    with TestClient(app) as broken:
        assert broken.get("/healthz").status_code == 200
        assert broken.get("/readyz").status_code == 503
        assert broken.get("/notes").status_code == 503


def test_metrics_use_route_template(client):
    note_id = client.post("/notes", json={"text": "a"}).json()["id"]
    client.get(f"/notes/{note_id}")
    client.get("/notes/424242")
    client.get("/no-such-path")
    client.get("/healthz")

    body = client.get("/metrics").text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds_bucket" in body
    assert 'path="/notes/{note_id}"' in body
    assert f'path="/notes/{note_id}"' not in body
    assert 'path="unmatched"' in body
    assert 'status="404"' in body
    assert 'path="/healthz"' not in body
