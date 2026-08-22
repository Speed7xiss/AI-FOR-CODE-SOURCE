def test_create_and_list_conversation(client):
    resp = client.post("/api/conversations", json={"title": "Teste"})
    assert resp.status_code == 200
    conv = resp.json()
    assert conv["title"] == "Teste"

    resp = client.get("/api/conversations")
    assert resp.status_code == 200
    assert any(c["id"] == conv["id"] for c in resp.json())


def test_get_nonexistent_conversation_returns_404(client):
    resp = client.get("/api/conversations/does-not-exist")
    assert resp.status_code == 404


def test_delete_conversation(client):
    conv = client.post("/api/conversations", json={}).json()
    resp = client.delete(f"/api/conversations/{conv['id']}")
    assert resp.status_code == 200
    assert client.get(f"/api/conversations/{conv['id']}").status_code == 404
