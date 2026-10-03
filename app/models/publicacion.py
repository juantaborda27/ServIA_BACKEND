import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EstadoPublicacionEnum, NivelUrgenciaEnum


class Publicacion(Base):
    __tablename__ = "publicaciones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    categoria_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categorias.id"), nullable=False
    )
    urgencia: Mapped[str] = mapped_column(NivelUrgenciaEnum, nullable=False)
    # NOTA: en la DB el default es auth.uid() (función de Supabase Auth).
    # No se replica aquí: asigna este valor desde tu lógica de negocio
    # (id del usuario autenticado) al crear la publicación.
    usuario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("usuarios.id"), nullable=False
    )
    estado: Mapped[str] = mapped_column(
        EstadoPublicacionEnum, nullable=False, server_default="activo"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    categoria: Mapped["Categoria"] = relationship(back_populates="publicaciones")
    usuario: Mapped["Usuario"] = relationship(back_populates="publicaciones")
    postulaciones: Mapped[list["Postulacion"]] = relationship(
        back_populates="publicacion", cascade="all, delete-orphan"
    )
