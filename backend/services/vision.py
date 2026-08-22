"""
Serviço de análise de imagens (screenshots de erro, diagramas, UI, etc.).
Reaproveita o LLMProvider configurado — só funciona se VISION_MODEL estiver
definido no .env.
"""
from services.llm import LLMProvider


async def analyze_images(
    provider: LLMProvider, message: str, history: list[dict], image_paths: list[str]
) -> str:
    if not image_paths:
        raise ValueError("Nenhuma imagem fornecida para análise.")
    return await provider.generate_with_images(message, history, image_paths)
