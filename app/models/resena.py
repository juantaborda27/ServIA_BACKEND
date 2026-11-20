import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Resena(Base):
    __tablename__ = "resenas"
    __table_args__ = (
        UniqueConstraint(
            "publicacion_id", "cliente_id", name="uq_resena_publicacion_cliente"
        ),
        CheckConstraint("calificacion >= 1 AND calificacion <= 5", name="resenas_calificacion_check"),
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
    cliente_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id", ondelete="CASCADE"),
        nullable=False,
    )
    prestador_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("prestadores.id", ondelete="CASCADE"),
        nullable=False,
    )
    calificacion: Mapped[int] = mapped_column(Integer, nullable=False)
    comentario: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    publicacion: Mapped["Publicacion"] = relationship(back_populates="resenas")
    cliente: Mapped["Usuario"] = relationship(foreign_keys=[cliente_id])
    prestador: Mapped["Prestador"] = relationship(back_populates="resenas", foreign_keys=[prestador_id])
