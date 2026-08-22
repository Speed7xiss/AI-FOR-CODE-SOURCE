"""
Runa AI — Backend (FastAPI)

Inicia a aplicação, registra rotas, CORS e cria as tabelas do banco.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config import get_settings
from database import init_db
from routes import chat, conversations, files, health

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("runa.main")

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("%s iniciado (ambiente=%s)", settings.APP_NAME, settings.ENVIRONMENT)
    yield


app = FastAPI(title=settings.APP_NAME, version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(chat.router)
app.include_router(files.router)
app.include_router(conversations.router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    """Nunca vaza stack traces para o cliente — apenas loga internamente."""
    logger.exception("Erro não tratado em %s", request.url.path)
    return JSONResponse(
        status_code=500, content={"detail": "Ocorreu um erro interno no servidor."}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.get("/")
def root():
    return {"app": settings.APP_NAME, "status": "online"}
