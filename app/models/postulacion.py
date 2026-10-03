import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import EstadoPostulacionEnum


class Postulacion(Base):
    __tablename__ = "postulaciones"
    __table_args__ = (
        UniqueConstraint(
            "publicacion_id", "prestador_id", name="uq_prestador_solicitud"
        ),
        CheckConstraint("precio_ofertado > 0", name="postulaciones_precio_ofertado_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    publicacion_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("publicaciones.id", ondelete="CASCADE"),
        nullable=False,
    )
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prestadores.id", ondelete="CASCADE"),
        nullable=False,
    )
    precio_ofertado: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    disponibilidad: Mapped[str] = mapped_column(String(100), nullable=False)
    mensaje: Mapped[str] = mapped_column(Text, nullable=False)
    estado: Mapped[str] = mapped_column(
        EstadoPostulacionEnum, nullable=False, server_default="pendiente"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    # NOTA: la tabla tiene un trigger trg_postulaciones_updated_at que
    # actualiza updated_at automáticamente en cada UPDATE (vía función
    # set_updated_at() en la base de datos). No necesitas replicarlo en
    # Python; ocurre a nivel de Postgres.

    publicacion: Mapped["Publicacion"] = relationship(back_populates="postulaciones")
    prestador: Mapped["Prestador"] = relationship(back_populates="postulaciones")
