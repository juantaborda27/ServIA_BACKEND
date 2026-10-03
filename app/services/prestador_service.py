from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import inspect

from app.repositories.prestador_repository import PrestadorRepository
from app.schemas.prestador import PrestadorCreate, PrestadorUpdate


class PrestadorService:

    def __init__(self, repository: PrestadorRepository):
        self.repository = repository

    async def create_prestador(self, data: PrestadorCreate, user_id: str):

        payload = data.model_dump(mode="json", exclude={"categoria_ids"})
        payload["id"] = user_id

        prestador = await self.repository.create(payload)

        if not prestador:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear el prestador"
            )

        if data.categoria_ids:
            await self.repository.add_especialidades(user_id, [str(cid) for cid in data.categoria_ids])

        return await self.get_prestador(user_id)

    async def get_prestador(self, prestador_id: str):

        prestador = await self.repository.get_by_id(prestador_id)

        if not prestador:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prestador no encontrado"
            )

        return self._flatten_categorias(prestador)

    async def list_prestadores(
        self,
        disponible: Optional[bool] = None,
        verificado: Optional[bool] = None,
        categoria_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ):

        prestadores = await self.repository.list_all(
            disponible=disponible,
            verificado=verificado,
            categoria_id=categoria_id,
            limit=limit,
            offset=offset,
        )

        return [self._flatten_categorias(p) for p in prestadores]

    async def update_prestador(
        self,
        prestador_id: str,
        data: PrestadorUpdate,
        user_id: str,
    ):

        prestador = await self.get_prestador(prestador_id)
        await self._verificar_dueno(prestador, user_id)

        update_data = data.model_dump(exclude_unset=True, mode="json", exclude={"categoria_ids"})

        if update_data:
            await self.repository.update(prestador_id, update_data)

        if data.categoria_ids is not None:
            await self.repository.replace_especialidades(
                prestador_id, [str(cid) for cid in data.categoria_ids]
            )

        return await self.get_prestador(prestador_id)

    async def delete_prestador(self, prestador_id: str, user_id: str):

        prestador = await self.get_prestador(prestador_id)
        await self._verificar_dueno(prestador, user_id)

        await self.repository.delete(prestador_id)

        return {"message": "Prestador eliminado correctamente"}

    @staticmethod
    async def _verificar_dueno(prestador: dict, user_id: str):

        if str(prestador["id"]) != str(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso sobre este prestador"
            )

    @staticmethod
    def _model_to_dict(obj) -> Optional[dict]:
        if obj is None:
            return None
        return {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}

    @classmethod
    def _flatten_categorias(cls, prestador) -> dict:

        data = cls._model_to_dict(prestador)

        # Aplanar datos del usuario relacionado (antes: prestador.pop("usuario", None))
        usuario = getattr(prestador, "usuario", None)
        if usuario:
            data["nombre_completo"] = usuario.nombre_completo
            data["telefono"] = usuario.telefono
            data["foto_perfil"] = usuario.foto_perfil
            data["ubicacion"] = usuario.ubicacion
            data["fecha_registro"] = usuario.fecha_registro
            data["activo"] = usuario.activo

        # Aplanar categorías a través de la relación especialidades -> categoria
        # (antes: prestador.pop("categorias", []))
        especialidades = getattr(prestador, "especialidades", []) or []

        data["categorias"] = [
            cls._model_to_dict(esp.categoria)
            for esp in especialidades if getattr(esp, "categoria", None)
        ]

        return data