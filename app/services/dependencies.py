from fastapi import Depends

from app.repositories.dependencias import (
    get_postulacion_repository,
    get_prestador_repository,
    get_publicacion_repository,
    get_servicio_repository,
    get_usuario_repository,
)
from app.repositories.postulacion_repository import PostulacionRepository
from app.repositories.prestador_repository import PrestadorRepository
from app.repositories.post_repository import PublicacionRepository
from app.repositories.servicio_repository import ServicioRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.usuario_service import UsuarioService
from app.services.servicio_service import ServicioService
from app.services.prestador_service import PrestadorService
from app.services.post_service import PublicacionService
from app.services.postulacion_service import PostulacionService

# Nota: agrega aquí PublicacionService, PrestadorService, PostulacionService y
# ServicioService siguiendo el mismo patrón cuando los conviertas (ver ejemplo
# de UsuarioService: reciben el repository por constructor, no lo crean ellos).


def get_usuario_service(
    repository: UsuarioRepository = Depends(get_usuario_repository),
) -> UsuarioService:
    return UsuarioService(repository)

def get_postulacion_service(
    repository: PostulacionRepository = Depends(get_postulacion_repository),
    publicacion_repository: PublicacionRepository = Depends(get_publicacion_repository),
) -> PostulacionService:
    return PostulacionService(repository, publicacion_repository)
def get_servicio_service(
    repository: ServicioRepository = Depends(get_servicio_repository),
) -> ServicioService:
    return ServicioService(repository)
def get_prestador_service(
    repository: PrestadorRepository = Depends(get_prestador_repository),
) -> PrestadorService:
    return PrestadorService(repository)
def get_publicacion_service(
    repository: PublicacionRepository = Depends(get_publicacion_repository),
) -> PublicacionService:
    return PublicacionService(repository)
def get_postulacion_service(
    repository: PostulacionRepository = Depends(get_postulacion_repository),
    publicacion_repository: PublicacionRepository = Depends(get_publicacion_repository),
) -> PostulacionService:
    return PostulacionService(repository, publicacion_repository)