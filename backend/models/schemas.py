"""
Schemas Pydantic (validação de entrada/saída da API).
"""
from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=20000)
    conversation_id: str | None = None
    model: str | None = Field(default=None, min_length=1, max_length=200)


class ChatResponse(BaseModel):
    response: str
    conversation_id: str


class MessageOut(BaseModel):
    id: str
    role: str
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class FileOut(BaseModel):
    id: str
    filename: str
    file_type: str
    size_bytes: int

    model_config = {"from_attributes": True}


class ConversationOut(BaseModel):
    id: str
    title: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConversationDetailOut(ConversationOut):
    messages: list[MessageOut] = []
    files: list[FileOut] = []


class ConversationCreate(BaseModel):
    title: str | None = None


class HealthOut(BaseModel):
    status: str
    ollama_reachable: bool
    model: str
    vision_model: str | None = None


class ModelOut(BaseModel):
    name: str
    size: int | None = None
    parameter_size: str | None = None
    family: str | None = None
    is_vision: bool = False


class ModelsOut(BaseModel):
    models: list[ModelOut]
    default_model: str | None = None
    vision_model: str | None = None
