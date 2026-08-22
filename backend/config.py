"""
Configuração central da Runa AI.
Todos os valores sensíveis/ajustáveis vêm de variáveis de ambiente (.env).
Nunca coloque segredos reais diretamente neste arquivo.
"""
import json
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


def _get_list(env_name: str, default: list[str]) -> list[str]:
    raw = os.getenv(env_name)
    if not raw:
        return default
    try:
        # aceita tanto JSON ("[\"a\",\"b\"]") quanto CSV simples ("a,b")
        if raw.strip().startswith("["):
            return json.loads(raw)
        return [item.strip() for item in raw.split(",") if item.strip()]
    except (json.JSONDecodeError, ValueError):
        return default


class Settings:
    # Aplicação
    APP_NAME: str = os.getenv("APP_NAME", "Runa AI")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Provedor de LLM ativo: "ollama" (modelos locais) ou "groq" (nuvem, rápido)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").strip().lower()

    # Ollama / LLM
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_API_KEY: str = os.getenv("OLLAMA_API_KEY", "")
    OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "")
    VISION_MODEL: str = os.getenv("VISION_MODEL", "")
    OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
    OLLAMA_DISCOVERY_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_DISCOVERY_TIMEOUT_SECONDS", "5"))

    # Groq (nuvem)
    GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
    # Aceita várias chaves separadas por vírgula; a Runa roda entre elas
    # automaticamente se uma bater rate limit (429) ou ficar inválida (401).
    GROQ_API_KEYS: list[str] = _get_list("GROQ_API_KEYS", [])
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
    # Opcional: modelo multimodal do Groq para análise de imagens (deixe vazio
    # para desabilitar e usar apenas VISION_MODEL do Ollama, se configurado).
    GROQ_VISION_MODEL: str = os.getenv("GROQ_VISION_MODEL", "")
    GROQ_TIMEOUT_SECONDS: int = int(os.getenv("GROQ_TIMEOUT_SECONDS", "120"))

    # Banco de dados
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./runa.db")

    # CORS
    CORS_ORIGINS: list[str] = _get_list(
        "CORS_ORIGINS", ["http://localhost:5500", "http://localhost:3000"]
    )

    # Upload / limites
    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "25"))
    MAX_FILES_PER_MESSAGE: int = int(os.getenv("MAX_FILES_PER_MESSAGE", "20"))
    MAX_ZIP_SIZE_MB: int = int(os.getenv("MAX_ZIP_SIZE_MB", "50"))
    MAX_FILES_IN_ZIP: int = int(os.getenv("MAX_FILES_IN_ZIP", "500"))
    MAX_ZIP_UNCOMPRESSED_MB: int = int(os.getenv("MAX_ZIP_UNCOMPRESSED_MB", "300"))
    MAX_ZIP_DEPTH: int = int(os.getenv("MAX_ZIP_DEPTH", "12"))
    MAX_CONTEXT_CHARS: int = int(os.getenv("MAX_CONTEXT_CHARS", "60000"))

    STORAGE_DIR: str = os.getenv("STORAGE_DIR", "./storage/uploads")

    ALLOWED_EXTENSIONS: set[str] = {
        ".c", ".cpp", ".h", ".hpp", ".cs", ".py", ".js", ".ts", ".jsx", ".tsx",
        ".java", ".rs", ".go", ".php", ".html", ".css", ".sql", ".json", ".xml",
        ".yaml", ".yml", ".md", ".txt", ".log", ".sh", ".ps1", ".zip",
        ".png", ".jpg", ".jpeg", ".webp",
    }

    IMAGE_EXTENSIONS: set[str] = {".png", ".jpg", ".jpeg", ".webp"}

    # Extensões que NUNCA devem ser executadas/aceitas dentro de um ZIP
    BLOCKED_EXECUTABLE_EXTENSIONS: set[str] = {
        ".exe", ".bat", ".cmd", ".com", ".msi", ".scr", ".dll", ".so", ".dylib",
    }


@lru_cache
def get_settings() -> Settings:
    return Settings()
