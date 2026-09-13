import uuid

from sqlalchemy import Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Categoria(Base):
    __tablename__ = "categorias"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    nombre: Mapped[str] = mapped_column(Text, nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text, nullable=True)
    icono: Mapped[str | None] = mapped_column(Text, nullable=True)

    publicaciones: Mapped[list["Publicacion"]] = relationship(back_populates="categoria")
    especialidades: Mapped[list["Especialidad"]] = relationship(
        back_populates="categoria", cascade="all, delete-orphan"
    )
    servicios: Mapped[list["Servicio"]] = relationship(back_populates="categoria")
