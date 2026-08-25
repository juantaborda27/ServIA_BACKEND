from fastapi import APIRouter, Depends, status
from app.schemas.servicio import ServicioCreate, ServicioUpdate, ServicioResponse
from app.services.servicio_service import ServicioService
from app.dependencies.auth import get_current_user # Tu dependencia actual

router = APIRouter(
    prefix="/prestador/servicios",
    tags=["Servicios Prestador"]
)

servicio_service = ServicioService()

@router.post("/", response_model=ServicioResponse, status_code=status.HTTP_201_CREATED)
def crear_servicio(
    data: ServicioCreate, 
    user: dict = Depends(get_current_user)
):
    return servicio_service.create_service(user.id, data)

@router.put("/{servicio_id}", response_model=ServicioResponse)
def editar_servicio(
    servicio_id: str, 
    data: ServicioUpdate, 
    user: dict = Depends(get_current_user)
):
    return servicio_service.update_service(servicio_id, user.id, data)

@router.patch("/{servicio_id}/publicar", response_model=ServicioResponse)
def publicar_servicio(
    servicio_id: str, 
    user: dict = Depends(get_current_user)
):
    return servicio_service.publish_service(servicio_id, user.id)

@router.delete("/{servicio_id}", status_code=status.HTTP_200_OK)
def eliminar_servicio(
    servicio_id: str, 
    user: dict = Depends(get_current_user)
):
    return servicio_service.delete_service(servicio_id, user.id)

