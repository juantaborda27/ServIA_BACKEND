from fastapi import HTTPException, status
from datetime import datetime, timezone
from app.repositories.servicio_repository import ServicioRepository
from app.schemas.servicio import ServicioCreate, ServicioUpdate

class ServicioService:
    def __init__(self, repository: ServicioRepository):
        self.repository = repository

    async def create_service(self, prestador_id: str, data: ServicioCreate):
        servicio_data = data.model_dump()
        servicio_data["prestador_id"] = prestador_id
        servicio_data["activo"] = False # Inicia inactivo hasta que se publique
        return await self.repository.create(servicio_data)

    async def update_service(self, servicio_id: str, prestador_id: str, data: ServicioUpdate):
        servicio = await self.repository.get_by_id(servicio_id)
        if not servicio or servicio["prestador_id"] != prestador_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado o acceso denegado")
            
        update_data = data.model_dump(exclude_unset=True)
        return await self.repository.update(servicio_id, update_data)

    async def publish_service(self, servicio_id: str, prestador_id: str):
        servicio = await self.repository.get_by_id(servicio_id)
        if not servicio or servicio["prestador_id"] != prestador_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado")

        publish_data = {
            "activo": True,
            "fechaPublicacion": datetime.now(timezone.utc).isoformat()
        }
        return await self.repository.update(servicio_id, publish_data)

    async def delete_service(self, servicio_id: str, prestador_id: str):
        servicio = await self.repository.get_by_id(servicio_id)
        if not servicio or servicio["prestador_id"] != prestador_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Servicio no encontrado")

        await self.repository.delete(servicio_id)
        return {"message": "Servicio eliminado correctamente"}