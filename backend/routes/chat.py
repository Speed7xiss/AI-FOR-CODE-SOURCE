import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models.models import Conversation, Message, UploadedFile
from models.schemas import ChatRequest, ChatResponse
from services.file_analyzer import read_text_for_context
from services.llm import LLMError, get_llm_provider
from services.vision import analyze_images

router = APIRouter(prefix="/api", tags=["chat"])
logger = logging.getLogger("runa.chat")
settings = get_settings()


def _build_history(conversation: Conversation) -> list[dict]:
    """Converte as mensagens salvas em formato {role, content} para o LLM."""
    history = [{"role": m.role, "content": m.content} for m in conversation.messages]
    return history[-20:]  # limita o histórico para não estourar o contexto


def _build_files_context(files: list[UploadedFile]) -> tuple[str, list[str]]:
    """
    Monta um bloco de texto com o conteúdo relevante dos arquivos da conversa
    (código/texto e resumos de ZIP) e retorna também a lista de caminhos de imagem.
    """
    context_parts: list[str] = []
    image_paths: list[str] = []
    total_chars = 0

    for f in files:
        if f.file_type == "image":
            image_paths.append(f.stored_path)
            continue

        if f.file_type == "zip":
            overview_path = f.stored_path + ".overview.txt"
            try:
                with open(overview_path, "r", encoding="utf-8") as fh:
                    content = fh.read()
            except OSError:
                content = "[resumo do ZIP indisponível]"
            block = f"### Projeto ZIP: {f.filename}\n{content}\n"
        else:
            content = read_text_for_context(f.stored_path)
            block = f"### Arquivo: {f.filename}\n```\n{content}\n```\n"

        if total_chars + len(block) > settings.MAX_CONTEXT_CHARS:
            context_parts.append("... [contexto adicional truncado por limite de tamanho]")
            break

        context_parts.append(block)
        total_chars += len(block)

    return "\n".join(context_parts), image_paths


@router.post("/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest, db: Session = Depends(get_db)):
    if payload.conversation_id:
        conversation = db.get(Conversation, payload.conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversa não encontrada.")
    else:
        conversation = Conversation(title=payload.message[:60])
        db.add(conversation)
        db.commit()
        db.refresh(conversation)

    history = _build_history(conversation)
    files_context, image_paths = _build_files_context(conversation.files)

    effective_message = payload.message
    if files_context:
        effective_message = (
            f"{payload.message}\n\n"
            f"--- Contexto de arquivos anexados nesta conversa ---\n{files_context}"
        )

    user_message = Message(conversation_id=conversation.id, role="user", content=payload.message)
    db.add(user_message)
    db.commit()

    provider = get_llm_provider()
    if payload.model and hasattr(provider, "use_model"):
        provider.use_model(payload.model)

    try:
        if image_paths:
            reply = await analyze_images(provider, effective_message, history, image_paths)
        else:
            reply = await provider.generate_response(effective_message, history)
    except LLMError as exc:
        logger.warning("Erro de LLM: %s", exc)
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception:
        logger.exception("Erro interno inesperado ao gerar resposta")
        raise HTTPException(
            status_code=500, detail="Ocorreu um erro interno ao processar sua mensagem."
        ) from None

    assistant_message = Message(conversation_id=conversation.id, role="assistant", content=reply)
    db.add(assistant_message)
    db.commit()

    return ChatResponse(response=reply, conversation_id=conversation.id)
