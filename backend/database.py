"""
Configuração do banco de dados (SQLAlchemy).
Usa SQLite por padrão; DATABASE_URL pode ser trocada para PostgreSQL
no futuro sem alterar o restante do código (a camada ORM é a mesma).
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from config import get_settings

settings = get_settings()

connect_args = {"check_same_thread": False} if settings.DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    """Dependency do FastAPI: entrega uma sessão e garante que ela é fechada."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """Cria as tabelas se ainda não existirem. Importa os models para registrá-los."""
    from models import models  # noqa: F401  (garante que os modelos sejam registrados)

    Base.metadata.create_all(bind=engine)
