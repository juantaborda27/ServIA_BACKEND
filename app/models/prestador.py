import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Prestador(Base):
    __tablename__ = "prestadores"

    # id es a la vez PK y FK -> relación 1:1 con usuarios
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        primary_key=True,
    )
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    disponible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    verificado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fecha_creacion: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    usuario: Mapped["Usuario"] = relationship(back_populates="prestador")
    especialidades: Mapped[list["Especialidad"]] = relationship(
        back_populates="prestador", cascade="all, delete-orphan"
    )
    servicios: Mapped[list["Servicio"]] = relationship(
        back_populates="prestador", cascade="all, delete-orphan"
    )
    postulaciones: Mapped[list["Postulacion"]] = relationship(
        back_populates="prestador", cascade="all, delete-orphan"
    )
