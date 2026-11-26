from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import UploadFile

from app.core.storage import image_storage
from app.services.usuario_service import UsuarioService


class FakeUsuarioRepository:
    def __init__(self, usuario):
        self.usuario = usuario

    async def get_by_id(self, user_id):
        return self.usuario if self.usuario.id == user_id else None

    async def update(self, user_id, data):
        if self.usuario.id != user_id:
            return None
        for key, value in data.items():
            setattr(self.usuario, key, value)
        return self.usuario


@pytest.mark.asyncio
async def test_upload_profile_photo_saves_shared_user_photo_and_replaces_old_file(monkeypatch):
    usuario = SimpleNamespace(
        id="user-1",
        nombre_completo="Usuario de prueba",
        foto_perfil="usuarios/user-1/perfil/anterior.jpg",
        hashed_password="not-returned",
    )
    repository = FakeUsuarioRepository(usuario)
    monkeypatch.setattr(
        image_storage,
        "upload_profile",
        AsyncMock(return_value=SimpleNamespace(key="usuarios/user-1/perfil/nueva.jpg")),
    )
    delete = AsyncMock()
    monkeypatch.setattr(image_storage, "delete", delete)
    monkeypatch.setattr(image_storage, "resolve_url", lambda key: f"signed:{key}" if key else None)

    result = await UsuarioService(repository).upload_profile_photo(
        "user-1",
        UploadFile(filename="perfil.jpg", file=BytesIO(b"image")),
    )

    assert usuario.foto_perfil == "usuarios/user-1/perfil/nueva.jpg"
    assert result["foto_perfil"] == "signed:usuarios/user-1/perfil/nueva.jpg"
    assert "hashed_password" not in result
    delete.assert_awaited_once_with("usuarios/user-1/perfil/anterior.jpg")
