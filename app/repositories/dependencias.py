from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.repositories.postulacion_repository import PostulacionRepository
from app.repositories.prestador_repository import PrestadorRepository
from app.repositories.post_repository import PublicacionRepository
from app.repositories.servicio_repository import ServicioRepository
from app.repositories.usuario_repository import UsuarioRepository


def get_publicacion_repository(
    db: AsyncSession = Depends(get_db),
) -> PublicacionRepository:
    return PublicacionRepository(db)


def get_prestador_repository(
    db: AsyncSession = Depends(get_db),
) -> PrestadorRepository:
    return PrestadorRepository(db)


def get_postulacion_repository(
    db: AsyncSession = Depends(get_db),
) -> PostulacionRepository:
    return PostulacionRepository(db)


def get_servicio_repository(
    db: AsyncSession = Depends(get_db),
) -> ServicioRepository:
    return ServicioRepository(db)


def get_usuario_repository(
    db: AsyncSession = Depends(get_db),
) -> UsuarioRepository:
    return UsuarioRepository(db)