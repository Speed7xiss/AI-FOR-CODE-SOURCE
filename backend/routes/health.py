from fastapi import APIRouter

from config import get_settings
from models.schemas import HealthOut, ModelOut, ModelsOut
from services.llm import get_llm_provider

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=HealthOut)
async def health_check():
    settings = get_settings()
    provider = get_llm_provider()
    reachable = await provider.is_available()
    if settings.LLM_PROVIDER == "groq":
        current_model = settings.GROQ_MODEL or "(não configurado)"
        vision_model = settings.GROQ_VISION_MODEL or None
    else:
        current_model = settings.OLLAMA_MODEL or "(não configurado)"
        vision_model = settings.VISION_MODEL or None
    return HealthOut(
        status="ok",
        ollama_reachable=reachable,
        model=current_model,
        vision_model=vision_model,
    )


@router.get("/models", response_model=ModelsOut)
async def list_models():
    settings = get_settings()
    provider = get_llm_provider()
    raw_models = await provider.list_models()
    vision_model = settings.GROQ_VISION_MODEL if settings.LLM_PROVIDER == "groq" else settings.VISION_MODEL
    default_model = settings.GROQ_MODEL if settings.LLM_PROVIDER == "groq" else settings.OLLAMA_MODEL
    models = [
        ModelOut(
            name=item.get("name", ""),
            size=item.get("size"),
            parameter_size=item.get("details", {}).get("parameter_size"),
            family=item.get("details", {}).get("family"),
            is_vision=item.get("name") == vision_model,
        )
        for item in raw_models
        if item.get("name")
    ]
    return ModelsOut(
        models=models,
        default_model=default_model or None,
        vision_model=vision_model or None,
    )
