import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Numeric, Text, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Servicio(Base):
    __tablename__ = "servicios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prestadores.id", ondelete="CASCADE"),
        nullable=False,
    )
    categoria_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("categorias.id", ondelete="RESTRICT"),
        nullable=False,
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False)
    precio_desde: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    precio_hasta: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    duracion_estimada: Mapped[int] = mapped_column(Integer, nullable=False)
    activo: Mapped[bool | None] = mapped_column(Boolean, default=False, nullable=True)
    fecha_publicacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    fecha_creacion: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=True
    )

    prestador: Mapped["Prestador"] = relationship(back_populates="servicios")
    categoria: Mapped["Categoria"] = relationship(back_populates="servicios")
