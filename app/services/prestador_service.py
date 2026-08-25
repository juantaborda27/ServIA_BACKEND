from typing import Optional

from fastapi import HTTPException, status

from app.repositories.prestador_repository import PrestadorRepository
from app.schemas.prestador import PrestadorCreate, PrestadorUpdate


class PrestadorService:

    def __init__(self):

        self.repository = PrestadorRepository()

    def create_prestador(self, data: PrestadorCreate, user_id: str):

        payload = data.model_dump(mode="json", exclude={"categoria_ids"})
        payload["id"] = user_id

        prestador = self.repository.create(payload)

        if not prestador:

            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No se pudo crear el prestador"
            )

        if data.categoria_ids:
            self.repository.add_especialidades(user_id, [str(cid) for cid in data.categoria_ids])

        return self.get_prestador(user_id)

    def get_prestador(self, prestador_id: str):

        prestador = self.repository.get_by_id(prestador_id)

        if not prestador:

            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Prestador no encontrado"
            )

        return self._flatten_categorias(prestador)

    def list_prestadores(
        self,
        disponible: Optional[bool] = None,
        verificado: Optional[bool] = None,
        categoria_id: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ):

        prestadores = self.repository.list(
            disponible=disponible,
            verificado=verificado,
            categoria_id=categoria_id,
            limit=limit,
            offset=offset,
        )

        return [self._flatten_categorias(p) for p in prestadores]

    def update_prestador(
        self,
        prestador_id: str,
        data: PrestadorUpdate,
        user_id: str,
    ):

        prestador = self.get_prestador(prestador_id)
        self._verificar_dueno(prestador, user_id)

        update_data = data.model_dump(exclude_unset=True, mode="json", exclude={"categoria_ids"})

        if update_data:
            self.repository.update(prestador_id, update_data)

        if data.categoria_ids is not None:
            self.repository.replace_especialidades(
                prestador_id, [str(cid) for cid in data.categoria_ids]
            )

        return self.get_prestador(prestador_id)

    def delete_prestador(self, prestador_id: str, user_id: str):

        prestador = self.get_prestador(prestador_id)
        self._verificar_dueno(prestador, user_id)

        self.repository.delete(prestador_id)

        return {"message": "Prestador eliminado correctamente"}

    @staticmethod
    def _verificar_dueno(prestador: dict, user_id: str):

        if prestador["id"] != user_id:

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permiso sobre este prestador"
            )

    @staticmethod
    def _flatten_categorias(prestador: dict) -> dict:

        raw = prestador.pop("categorias", []) or []

        prestador["categorias"] = [
            item["categoria"] for item in raw if item.get("categoria")
        ]

        return prestador