"""
Abstração de provedor de LLM.

A Runa AI não fica presa a um único backend de modelo: qualquer provedor
novo (OpenAI-compatible, LM Studio, etc.) só precisa implementar
LLMProvider. Hoje só existe o OllamaProvider.
"""
import base64
import logging
from abc import ABC, abstractmethod

import httpx

from config import get_settings

logger = logging.getLogger("runa.llm")

SYSTEM_PROMPT = (
    "Você é a Runa AI, uma assistente de programação experiente. "
    "Priorize correção, segurança, simplicidade e manutenibilidade. "
    "Não invente APIs, bibliotecas ou comandos que não existem. "
    "Quando não tiver certeza de algo, diga isso explicitamente. "
    "Quando responder com código, use blocos markdown com a linguagem correta."
)


class LLMError(Exception):
    """Erro amigável de LLM, seguro para exibir ao usuário final."""


class LLMProvider(ABC):
    @abstractmethod
    async def generate_response(self, message: str, history: list[dict]) -> str:
        """Gera uma resposta de texto a partir da mensagem + histórico da conversa."""

    @abstractmethod
    async def generate_with_images(
        self, message: str, history: list[dict], image_paths: list[str]
    ) -> str:
        """Gera uma resposta considerando imagens anexadas (modelo multimodal)."""

    @abstractmethod
    async def is_available(self) -> bool:
        """Verifica se o backend do modelo está acessível."""


def _build_messages(message: str, history: list[dict]) -> list[dict]:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": message})
    return messages


class OllamaProvider(LLMProvider):
    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.OLLAMA_BASE_URL.rstrip("/")
        self.selected_model: str | None = None

    def _headers(self) -> dict[str, str]:
        if self.settings.OLLAMA_API_KEY:
            return {"Authorization": f"Bearer {self.settings.OLLAMA_API_KEY}"}
        return {}

    async def list_models(self) -> list[dict]:
        try:
            async with httpx.AsyncClient(timeout=self.settings.OLLAMA_DISCOVERY_TIMEOUT_SECONDS) as client:
                resp = await client.get(f"{self.base_url}/api/tags", headers=self._headers())
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Não foi possível listar modelos Ollama: %s", exc)
            return []
        return resp.json().get("models", [])

    def use_model(self, model: str | None) -> None:
        self.selected_model = model

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags", headers=self._headers())
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def generate_response(self, message: str, history: list[dict]) -> str:
        model = self.selected_model or self.settings.OLLAMA_MODEL
        if not model:
            raise LLMError(
                "Nenhum modelo Ollama configurado. Defina OLLAMA_MODEL no arquivo .env."
            )

        payload = {
            "model": model,
            "messages": _build_messages(message, history),
            "stream": False,
        }
        return await self._call_chat(payload)

    async def generate_with_images(
        self, message: str, history: list[dict], image_paths: list[str]
    ) -> str:
        if not self.settings.VISION_MODEL:
            raise LLMError(
                "O modelo atual não possui suporte a imagens. "
                "Configure VISION_MODEL no .env para habilitar análise de imagens."
            )

        images_b64 = []
        for path in image_paths:
            with open(path, "rb") as f:
                images_b64.append(base64.b64encode(f.read()).decode("utf-8"))

        messages = _build_messages(message, history)
        # anexa as imagens à última mensagem do usuário (formato Ollama)
        messages[-1]["images"] = images_b64

        payload = {
            "model": self.settings.VISION_MODEL,
            "messages": messages,
            "stream": False,
        }
        return await self._call_chat(payload)

    async def _call_chat(self, payload: dict) -> str:
        try:
            async with httpx.AsyncClient(timeout=self.settings.OLLAMA_TIMEOUT_SECONDS) as client:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload, headers=self._headers())
        except httpx.ConnectError as exc:
            logger.error("Falha ao conectar ao Ollama: %s", exc)
            raise LLMError(
                "Não foi possível conectar ao modelo configurado. "
                "Verifique se o Ollama está em execução em "
                f"{self.base_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            logger.error("Timeout ao chamar o Ollama: %s", exc)
            raise LLMError(
                "O modelo demorou demais para responder (timeout). Tente novamente "
                "ou reduza o tamanho do contexto enviado."
            ) from exc
        except httpx.HTTPError as exc:
            logger.error("Erro HTTP ao chamar o Ollama: %s", exc)
            raise LLMError("Ocorreu um erro ao se comunicar com o modelo.") from exc

        if resp.status_code == 404:
            raise LLMError(
                f"O modelo '{payload['model']}' não foi encontrado no Ollama. "
                f"Rode 'ollama pull {payload['model']}' e tente novamente."
            )
        if resp.status_code != 200:
            logger.error("Ollama retornou status %s: %s", resp.status_code, resp.text[:500])
            raise LLMError("O modelo retornou um erro inesperado.")

        data = resp.json()
        content = data.get("message", {}).get("content", "")
        if not content:
            raise LLMError("O modelo retornou uma resposta vazia.")
        return content


class GroqProvider(LLMProvider):
    """
    Provedor de nuvem usando a API da Groq (compatível com o formato OpenAI).
    Suporta múltiplas chaves em GROQ_API_KEYS: se uma chave bater rate limit
    (429) ou estiver inválida (401), a próxima é tentada automaticamente.
    """

    def __init__(self):
        self.settings = get_settings()
        self.base_url = self.settings.GROQ_BASE_URL.rstrip("/")
        self.keys = list(self.settings.GROQ_API_KEYS)
        self._key_index = 0
        self.selected_model: str | None = None

    def use_model(self, model: str | None) -> None:
        self.selected_model = model

    def _headers(self, key: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {key}"}

    async def is_available(self) -> bool:
        if not self.keys:
            return False
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(
                    f"{self.base_url}/models", headers=self._headers(self.keys[0])
                )
                return resp.status_code == 200
        except httpx.HTTPError:
            return False

    async def list_models(self) -> list[dict]:
        if not self.keys:
            return []
        try:
            async with httpx.AsyncClient(timeout=self.settings.OLLAMA_DISCOVERY_TIMEOUT_SECONDS) as client:
                resp = await client.get(
                    f"{self.base_url}/models", headers=self._headers(self.keys[0])
                )
                resp.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("Não foi possível listar modelos Groq: %s", exc)
            return []
        data = resp.json().get("data", [])
        return [
            {
                "name": item.get("id"),
                "details": {"parameter_size": None, "family": item.get("owned_by")},
                "size": item.get("context_window"),
            }
            for item in data
            if item.get("id")
        ]

    async def generate_response(self, message: str, history: list[dict]) -> str:
        if not self.keys:
            raise LLMError(
                "Nenhuma chave da Groq configurada. Defina GROQ_API_KEYS no arquivo .env."
            )
        model = self.selected_model or self.settings.GROQ_MODEL
        payload = {
            "model": model,
            "messages": _build_messages(message, history),
        }
        return await self._call_chat(payload)

    async def generate_with_images(
        self, message: str, history: list[dict], image_paths: list[str]
    ) -> str:
        if not self.settings.GROQ_VISION_MODEL:
            raise LLMError(
                "O modelo Groq atual não possui suporte a imagens. "
                "Configure GROQ_VISION_MODEL no .env para habilitar análise de imagens "
                "(ou troque para um provedor Ollama com VISION_MODEL configurado)."
            )

        content = [{"type": "text", "text": message}]
        for path in image_paths:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("utf-8")
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else "png"
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/{ext};base64,{b64}"},
                }
            )

        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({"role": "user", "content": content})

        payload = {"model": self.settings.GROQ_VISION_MODEL, "messages": messages}
        return await self._call_chat(payload)

    async def _call_chat(self, payload: dict) -> str:
        last_error: Exception | None = None
        attempts = max(len(self.keys), 1)

        for _ in range(attempts):
            key = self.keys[self._key_index % len(self.keys)]
            try:
                async with httpx.AsyncClient(timeout=self.settings.GROQ_TIMEOUT_SECONDS) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=self._headers(key),
                    )
            except httpx.ConnectError as exc:
                logger.error("Falha ao conectar à Groq: %s", exc)
                raise LLMError("Não foi possível conectar à API da Groq.") from exc
            except httpx.TimeoutException as exc:
                logger.error("Timeout ao chamar a Groq: %s", exc)
                raise LLMError("O modelo demorou demais para responder (timeout).") from exc
            except httpx.HTTPError as exc:
                logger.error("Erro HTTP ao chamar a Groq: %s", exc)
                raise LLMError("Ocorreu um erro ao se comunicar com a Groq.") from exc

            if resp.status_code == 200:
                data = resp.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                if not content:
                    raise LLMError("O modelo retornou uma resposta vazia.")
                return content

            if resp.status_code in (401, 429):
                # chave inválida ou rate-limited: tenta a próxima chave
                logger.warning(
                    "Chave Groq #%s retornou %s, tentando próxima chave...",
                    self._key_index,
                    resp.status_code,
                )
                last_error = LLMError(
                    "Todas as chaves da Groq configuradas estão inválidas ou sem cota no momento."
                )
                self._key_index += 1
                continue

            if resp.status_code == 404:
                raise LLMError(
                    f"O modelo '{payload['model']}' não foi encontrado na Groq. "
                    "Verifique GROQ_MODEL no .env (veja console.groq.com/docs/models)."
                )

            logger.error("Groq retornou status %s: %s", resp.status_code, resp.text[:500])
            raise LLMError("O modelo retornou um erro inesperado.")

        raise last_error or LLMError("Não foi possível obter resposta da Groq.")


def get_llm_provider() -> LLMProvider:
    """Ponto único de troca de provedor: escolhido via LLM_PROVIDER no .env."""
    settings = get_settings()
    if settings.LLM_PROVIDER == "groq":
        return GroqProvider()
    return OllamaProvider()
