import routes.chat as chat_module
from services.llm import LLMError


class FakeProvider:
    async def generate_response(self, message, history):
        return f"Resposta simulada para: {message[:30]}"

    async def generate_with_images(self, message, history, image_paths):
        return "Resposta simulada com imagem"

    async def is_available(self):
        return True


class FailingProvider:
    async def generate_response(self, message, history):
        raise LLMError("Não foi possível conectar ao modelo configurado.")

    async def generate_with_images(self, message, history, image_paths):
        raise LLMError("Não foi possível conectar ao modelo configurado.")

    async def is_available(self):
        return False


def test_chat_creates_conversation_and_replies(client, monkeypatch):
    monkeypatch.setattr(chat_module, "get_llm_provider", lambda: FakeProvider())

    resp = client.post("/api/chat", json={"message": "Olá, Runa"})
    assert resp.status_code == 200
    body = resp.json()
    assert "Resposta simulada" in body["response"]
    assert body["conversation_id"]


def test_chat_with_ollama_offline_returns_friendly_error(client, monkeypatch):
    monkeypatch.setattr(chat_module, "get_llm_provider", lambda: FailingProvider())

    resp = client.post("/api/chat", json={"message": "Olá"})
    assert resp.status_code == 502
    assert "conectar" in resp.json()["detail"]


def test_chat_rejects_empty_message(client):
    resp = client.post("/api/chat", json={"message": ""})
    assert resp.status_code == 422
