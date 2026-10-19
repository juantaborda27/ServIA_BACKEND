import uuid
from datetime import datetime
from sqlalchemy import text
from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Mensaje(Base):
    __tablename__ = "mensajes"

    id_mensaje: Mapped[uuid.UUID] = mapped_column(
    UUID(as_uuid=True),
    primary_key=True,
    server_default=text("gen_random_uuid()"),
    )

    contenido: Mapped[str] = mapped_column(Text, nullable=False)

    fecha_hora: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        server_default=func.now(),
    )

    id_conversacion: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversaciones.id_conversacion", ondelete="CASCADE"),
    )

    id_remitente: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id"),
    )

    id_destinatario: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("usuarios.id"),
    )

    conversacion: Mapped["Conversacion | None"] = relationship(
        back_populates="mensajes",
    )

    remitente: Mapped["Usuario | None"] = relationship(
        foreign_keys=[id_remitente],
        back_populates="mensajes_enviados",
    )

    destinatario: Mapped["Usuario | None"] = relationship(
        foreign_keys=[id_destinatario],
        back_populates="mensajes_recibidos",
    )
