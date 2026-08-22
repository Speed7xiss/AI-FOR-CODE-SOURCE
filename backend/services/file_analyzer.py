"""
Validação, armazenamento e leitura segura de arquivos enviados pelo usuário.

Regras de segurança:
- apenas extensões da whitelist são aceitas;
- nome de arquivo é sanitizado (sem caminhos, sem caracteres perigosos);
- tamanho máximo é aplicado;
- nenhum arquivo é executado — apenas lido como texto/binário para contexto.
"""
import os
import re
import uuid

from fastapi import UploadFile

from config import get_settings

settings = get_settings()

_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class FileValidationError(Exception):
    """Erro amigável de validação de arquivo."""


def sanitize_filename(filename: str) -> str:
    """Remove qualquer componente de caminho e caracteres perigosos do nome."""
    base = os.path.basename(filename)
    base = _SAFE_NAME_RE.sub("_", base)
    return base or "arquivo"


def get_extension(filename: str) -> str:
    return os.path.splitext(filename)[1].lower()


def classify_file(filename: str) -> str:
    ext = get_extension(filename)
    if ext == ".zip":
        return "zip"
    if ext in settings.IMAGE_EXTENSIONS:
        return "image"
    return "code" if ext not in {".md", ".txt", ".log"} else "text"


def validate_upload(filename: str, size_bytes: int) -> None:
    ext = get_extension(filename)
    if ext in settings.BLOCKED_EXECUTABLE_EXTENSIONS:
        raise FileValidationError(f"Arquivos '{ext}' não são permitidos por segurança.")
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise FileValidationError(f"Extensão '{ext}' não é suportada.")

    max_bytes = settings.MAX_ZIP_SIZE_MB if ext == ".zip" else settings.MAX_UPLOAD_SIZE_MB
    max_bytes *= 1024 * 1024
    if size_bytes > max_bytes:
        limit_mb = settings.MAX_ZIP_SIZE_MB if ext == ".zip" else settings.MAX_UPLOAD_SIZE_MB
        raise FileValidationError(f"Arquivo maior que o limite permitido ({limit_mb} MB).")


async def save_upload(upload: UploadFile, conversation_id: str) -> tuple[str, str, int]:
    """
    Salva o arquivo em disco dentro de storage/uploads/{conversation_id}/.
    Retorna (nome_sanitizado, caminho_salvo, tamanho_em_bytes).
    """
    safe_name = sanitize_filename(upload.filename or "arquivo")

    content = await upload.read()
    validate_upload(safe_name, len(content))

    conv_dir = os.path.join(settings.STORAGE_DIR, conversation_id)
    os.makedirs(conv_dir, exist_ok=True)

    unique_name = f"{uuid.uuid4().hex[:8]}_{safe_name}"
    dest_path = os.path.join(conv_dir, unique_name)

    with open(dest_path, "wb") as f:
        f.write(content)

    return safe_name, dest_path, len(content)


def read_text_for_context(path: str, max_chars: int = 8000) -> str:
    """Lê um arquivo de texto/código de forma segura para usar como contexto do LLM."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            data = f.read(max_chars + 1)
    except OSError:
        return "[não foi possível ler o arquivo]"

    if len(data) > max_chars:
        data = data[:max_chars] + "\n... [conteúdo truncado]"
    return data
