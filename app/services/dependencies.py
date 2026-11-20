from fastapi import Depends

from app.repositories.dependencias import (
    get_postulacion_repository,
    get_prestador_repository,
    get_publicacion_repository,
    get_resena_repository,
    get_notificacion_repository,
    get_servicio_repository,
    get_usuario_repository,
    get_conversacion_repository,
    get_mensaje_repository
)
from app.repositories.notificacion_repository import NotificacionRepository
from app.repositories.postulacion_repository import PostulacionRepository
from app.repositories.prestador_repository import PrestadorRepository
from app.repositories.post_repository import PublicacionRepository
from app.repositories.resena_repository import ResenaRepository
from app.repositories.servicio_repository import ServicioRepository
from app.repositories.usuario_repository import UsuarioRepository
from app.services.usuario_service import UsuarioService
from app.services.servicio_service import ServicioService
from app.services.prestador_service import PrestadorService
from app.services.post_service import PublicacionService
from app.services.postulacion_service import PostulacionService
<<<<<<< HEAD
from app.services.mensaje_service import MensajeService
from app.services.conversacion_service import ConversacionService
from app.repositories.conversacion_repository import ConversacionRepository
from app.repositories.mensaje_repository import MensajeRepository

# Nota: agrega aquí PublicacionService, PrestadorService, PostulacionService y
# ServicioService siguiendo el mismo patrón cuando los conviertas (ver ejemplo
# de UsuarioService: reciben el repository por constructor, no lo crean ellos).
=======
from app.services.resena_service import ResenaService
<<<<<<< HEAD
>>>>>>> 610bbb7 (reseñas e historial de trabajo)
=======
from app.services.notificacion_service import NotificacionService
>>>>>>> ffcece1 (feat: actualizacion pantallas y notificaciones)


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
<<<<<<< HEAD
def get_postulacion_service(
    repository: PostulacionRepository = Depends(get_postulacion_repository),
    publicacion_repository: PublicacionRepository = Depends(get_publicacion_repository),
) -> PostulacionService:
    return PostulacionService(repository, publicacion_repository)

def get_mensaje_service(
    repository: MensajeRepository = Depends(get_mensaje_repository),
) -> MensajeService:
    return MensajeService(repository)

def get_conversacion_service(
    repository: ConversacionRepository = Depends(get_conversacion_repository),
) -> ConversacionService:
    return ConversacionService(repository)
=======


def get_resena_service(
    repository: ResenaRepository = Depends(get_resena_repository),
    post_repository: PublicacionRepository = Depends(get_publicacion_repository),
) -> ResenaService:
    return ResenaService(repository, post_repository)
<<<<<<< HEAD
>>>>>>> 610bbb7 (reseñas e historial de trabajo)
=======


def get_notificacion_service(
    repository: NotificacionRepository = Depends(get_notificacion_repository),
) -> NotificacionService:
    return NotificacionService(repository)
>>>>>>> ffcece1 (feat: actualizacion pantallas y notificaciones)
