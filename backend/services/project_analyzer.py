"""
Análise segura de projetos enviados em .zip.

Medidas de segurança implementadas:
- validação de que o arquivo é realmente um ZIP válido;
- proteção contra ZIP Slip / path traversal (nenhum membro pode escapar
  do diretório de extração);
- limite de quantidade de arquivos dentro do ZIP;
- limite de tamanho descompactado total (proteção contra zip bomb);
- limite de profundidade de diretórios;
- extração em diretório temporário isolado, removido ao final;
- nenhum arquivo extraído é executado.
"""
import os
import shutil
import tempfile
import zipfile

from config import get_settings

settings = get_settings()

LANGUAGE_BY_EXT = {
    ".py": "Python", ".js": "JavaScript", ".ts": "TypeScript", ".jsx": "JavaScript (React)",
    ".tsx": "TypeScript (React)", ".java": "Java", ".c": "C", ".h": "C", ".cpp": "C++",
    ".hpp": "C++", ".cs": "C#", ".rs": "Rust", ".go": "Go", ".php": "PHP",
    ".html": "HTML", ".css": "CSS", ".sql": "SQL", ".sh": "Shell", ".ps1": "PowerShell",
}

KEY_FILENAMES = {
    "package.json", "requirements.txt", "pyproject.toml", "readme.md", "dockerfile",
    "docker-compose.yml", ".env.example", "cargo.toml", "go.mod", "pom.xml",
    "csproj", "makefile",
}


class ZipValidationError(Exception):
    """Erro amigável de validação/segurança de ZIP."""


def _safe_extract_path(base_dir: str, member_name: str) -> str:
    """
    Resolve o caminho de destino de um membro do ZIP e garante que ele
    permanece dentro de base_dir (defesa contra ZIP Slip).
    """
    dest = os.path.normpath(os.path.join(base_dir, member_name))
    base_dir_abs = os.path.abspath(base_dir)
    dest_abs = os.path.abspath(dest)
    if not dest_abs.startswith(base_dir_abs + os.sep) and dest_abs != base_dir_abs:
        raise ZipValidationError(
            "O ZIP contém um caminho inválido (possível tentativa de path traversal)."
        )
    return dest_abs


def extract_zip_safely(zip_path: str) -> str:
    """
    Extrai o ZIP em um diretório temporário isolado, validando cada membro.
    Retorna o caminho do diretório temporário (o chamador é responsável por
    remover com cleanup_extracted()).
    """
    if not zipfile.is_zipfile(zip_path):
        raise ZipValidationError("O arquivo enviado não é um ZIP válido.")

    tmp_dir = tempfile.mkdtemp(prefix="runa_zip_")

    try:
        with zipfile.ZipFile(zip_path) as zf:
            infos = zf.infolist()

            if len(infos) > settings.MAX_FILES_IN_ZIP:
                raise ZipValidationError(
                    f"O ZIP contém mais de {settings.MAX_FILES_IN_ZIP} arquivos (limite excedido)."
                )

            total_uncompressed = 0
            max_uncompressed_bytes = settings.MAX_ZIP_UNCOMPRESSED_MB * 1024 * 1024

            for info in infos:
                # bloqueia caminhos absolutos e ".."
                if info.filename.startswith("/") or ".." in info.filename.split("/"):
                    raise ZipValidationError("O ZIP contém um caminho inválido.")

                depth = info.filename.count("/")
                if depth > settings.MAX_ZIP_DEPTH:
                    raise ZipValidationError("O ZIP excede a profundidade máxima de diretórios.")

                total_uncompressed += info.file_size
                if total_uncompressed > max_uncompressed_bytes:
                    raise ZipValidationError(
                        "O conteúdo descompactado do ZIP excede o limite permitido "
                        f"({settings.MAX_ZIP_UNCOMPRESSED_MB} MB)."
                    )

                dest_path = _safe_extract_path(tmp_dir, info.filename)

                if info.is_dir():
                    os.makedirs(dest_path, exist_ok=True)
                    continue

                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zf.open(info) as src, open(dest_path, "wb") as dst:
                    shutil.copyfileobj(src, dst)

        return tmp_dir
    except Exception:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise


def cleanup_extracted(tmp_dir: str) -> None:
    shutil.rmtree(tmp_dir, ignore_errors=True)


def build_project_overview(tmp_dir: str, max_chars: int = 6000) -> str:
    """
    Percorre o diretório extraído e monta um resumo textual do projeto:
    estrutura, linguagens detectadas e arquivos-chave. Não executa nada.
    """
    languages: dict[str, int] = {}
    key_files: list[str] = []
    tree_lines: list[str] = []
    file_count = 0

    for root, dirs, files in os.walk(tmp_dir):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv"}]
        rel_root = os.path.relpath(root, tmp_dir)
        for name in sorted(files):
            file_count += 1
            ext = os.path.splitext(name)[1].lower()
            if ext in LANGUAGE_BY_EXT:
                languages[LANGUAGE_BY_EXT[ext]] = languages.get(LANGUAGE_BY_EXT[ext], 0) + 1
            if name.lower() in KEY_FILENAMES or ext == ".csproj":
                rel_path = name if rel_root == "." else f"{rel_root}/{name}"
                key_files.append(rel_path)
            if len(tree_lines) < 200:
                rel_path = name if rel_root == "." else f"{rel_root}/{name}"
                tree_lines.append(rel_path)

    lang_summary = ", ".join(f"{lang} ({n} arquivo(s))" for lang, n in sorted(
        languages.items(), key=lambda kv: -kv[1]
    )) or "nenhuma linguagem reconhecida"

    key_summary = ", ".join(key_files) if key_files else "nenhum arquivo de configuração comum encontrado"

    tree_preview = "\n".join(tree_lines[:100])
    if len(tree_lines) > 100:
        tree_preview += f"\n... e mais {len(tree_lines) - 100} arquivo(s)"

    overview = (
        f"Resumo do projeto enviado (.zip):\n"
        f"- Total de arquivos: {file_count}\n"
        f"- Linguagens detectadas: {lang_summary}\n"
        f"- Arquivos-chave: {key_summary}\n\n"
        f"Estrutura (parcial):\n{tree_preview}"
    )

    if len(overview) > max_chars:
        overview = overview[:max_chars] + "\n... [resumo truncado]"

    return overview
