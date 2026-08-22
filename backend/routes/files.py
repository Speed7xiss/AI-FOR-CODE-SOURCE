import logging

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from config import get_settings
from database import get_db
from models.models import Conversation, UploadedFile
from models.schemas import FileOut
from services.file_analyzer import FileValidationError, classify_file, save_upload
from services.project_analyzer import (
    ZipValidationError,
    build_project_overview,
    cleanup_extracted,
    extract_zip_safely,
)

router = APIRouter(prefix="/api/files", tags=["files"])
logger = logging.getLogger("runa.files")
settings = get_settings()


@router.post("/upload", response_model=FileOut)
async def upload_file(
    conversation_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversa não encontrada.")

    try:
        safe_name, stored_path, size = await save_upload(file, conversation_id)
    except FileValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    file_type = classify_file(safe_name)

    # Se for ZIP, extrai com segurança, monta o resumo do projeto e o
    # salva ao lado do arquivo original para ser usado como contexto no chat.
    if file_type == "zip":
        try:
            tmp_dir = extract_zip_safely(stored_path)
            try:
                overview = build_project_overview(tmp_dir)
            finally:
                cleanup_extracted(tmp_dir)
        except ZipValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception("Falha ao analisar ZIP")
            raise HTTPException(
                status_code=400, detail="Não foi possível analisar o ZIP enviado."
            ) from exc

        with open(stored_path + ".overview.txt", "w", encoding="utf-8") as f:
            f.write(overview)

    record = UploadedFile(
        conversation_id=conversation_id,
        filename=safe_name,
        stored_path=stored_path,
        file_type=file_type,
        size_bytes=size,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@router.get("/{conversation_id}", response_model=list[FileOut])
def list_files(conversation_id: str, db: Session = Depends(get_db)):
    return (
        db.query(UploadedFile)
        .filter(UploadedFile.conversation_id == conversation_id)
        .all()
    )


@router.delete("/{file_id}")
def delete_file(file_id: str, db: Session = Depends(get_db)):
    record = db.get(UploadedFile, file_id)
    if not record:
        raise HTTPException(status_code=404, detail="Arquivo não encontrado.")
    db.delete(record)
    db.commit()
    return {"deleted": True}
