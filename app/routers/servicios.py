from fastapi import APIRouter, Depends, status
from app.schemas.servicio import ServicioCreate, ServicioUpdate, ServicioResponse
from app.services.servicio_service import ServicioService
from app.dependencies.auth import get_current_user # Tu dependencia actual
from app.services.dependencies import get_servicio_service
router = APIRouter(
    prefix="/prestador/servicios",
    tags=["Servicios Prestador"]
)


@router.post("/", response_model=ServicioResponse, status_code=status.HTTP_201_CREATED)
async def crear_servicio(
    data: ServicioCreate, 
    user: dict = Depends(get_current_user),
    services: ServicioService = Depends(get_servicio_service)
):
    return await services.create_service(user.id, data)

@router.put("/{servicio_id}", response_model=ServicioResponse)
async def editar_servicio(
    servicio_id: str, 
    data: ServicioUpdate, 
    user: dict = Depends(get_current_user),
    services: ServicioService = Depends(get_servicio_service)
):
    return await services.update_service(servicio_id, user.id, data)

@router.patch("/{servicio_id}/publicar", response_model=ServicioResponse)
async def publicar_servicio(
    servicio_id: str, 
    user: dict = Depends(get_current_user),
    services: ServicioService = Depends(get_servicio_service)
):
    return await services.publish_service(servicio_id, user.id)

@router.delete("/{servicio_id}", status_code=status.HTTP_200_OK)
async def eliminar_servicio(
    servicio_id: str, 
    user: dict = Depends(get_current_user),
    services: ServicioService = Depends(get_servicio_service)
):
    return await services.delete_service(servicio_id, user.id)

