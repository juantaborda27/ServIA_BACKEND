import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Usuario(Base):
    __tablename__ = "usuarios"

    # FK 1:1 hacia auth.users(id), gestionada por Supabase Auth
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    nombre_completo: Mapped[str] = mapped_column(Text, nullable=False)
    telefono: Mapped[str | None] = mapped_column(Text, nullable=True)
    foto_perfil: Mapped[str | None] = mapped_column(Text, nullable=True)
    ubicacion: Mapped[str | None] = mapped_column(Text, nullable=True)
    fecha_registro: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    activo: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Relaciones 1:1 (creadas automáticamente por trigger en Supabase)
    cliente: Mapped["Cliente"] = relationship(
        back_populates="usuario", uselist=False, cascade="all, delete-orphan"
    )
    prestador: Mapped["Prestador"] = relationship(
        back_populates="usuario", uselist=False, cascade="all, delete-orphan"
    )

    # Relación 1:N
    publicaciones: Mapped[list["Publicacion"]] = relationship(
        back_populates="usuario", cascade="all, delete-orphan"
    )
