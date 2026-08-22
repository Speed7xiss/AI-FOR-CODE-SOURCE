import io
import os
import zipfile

import pytest
from services.project_analyzer import ZipValidationError, extract_zip_safely


def _create_conversation(client):
    return client.post("/api/conversations", json={}).json()["id"]


def test_upload_valid_code_file(client):
    conv_id = _create_conversation(client)
    content = b"print('ola mundo')"
    resp = client.post(
        f"/api/files/upload?conversation_id={conv_id}",
        files={"file": ("main.py", io.BytesIO(content), "text/x-python")},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["filename"] == "main.py"
    assert body["file_type"] == "code"


def test_upload_rejects_blocked_extension(client):
    conv_id = _create_conversation(client)
    resp = client.post(
        f"/api/files/upload?conversation_id={conv_id}",
        files={"file": ("virus.exe", io.BytesIO(b"MZ"), "application/octet-stream")},
    )
    assert resp.status_code == 400


def test_upload_rejects_nonexistent_conversation(client):
    resp = client.post(
        "/api/files/upload?conversation_id=nao-existe",
        files={"file": ("main.py", io.BytesIO(b"x"), "text/x-python")},
    )
    assert resp.status_code == 404


def test_upload_valid_zip_is_extracted_and_analyzed(client):
    conv_id = _create_conversation(client)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("src/main.py", "print('hi')")
        zf.writestr("README.md", "# projeto teste")
    buffer.seek(0)

    resp = client.post(
        f"/api/files/upload?conversation_id={conv_id}",
        files={"file": ("projeto.zip", buffer, "application/zip")},
    )
    assert resp.status_code == 200
    assert resp.json()["file_type"] == "zip"


def test_zip_slip_is_blocked(tmp_path):
    malicious_zip = tmp_path / "evil.zip"
    with zipfile.ZipFile(malicious_zip, "w") as zf:
        zf.writestr("../../etc/passwd", "conteudo malicioso")

    with pytest.raises(ZipValidationError):
        extract_zip_safely(str(malicious_zip))


def test_invalid_zip_file_is_rejected(tmp_path):
    fake_zip = tmp_path / "fake.zip"
    fake_zip.write_bytes(b"isso nao e um zip valido")

    with pytest.raises(ZipValidationError):
        extract_zip_safely(str(fake_zip))
