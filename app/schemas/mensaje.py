from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class MensajeCreate(BaseModel):
    id_remitente: UUID
    contenido: str = Field(..., min_length=1, max_length=500)
    id_conversacion: UUID
    id_destinatario: UUID


class MensajeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id_mensaje: UUID
    contenido: str
    id_conversacion: UUID | None
    id_remitente: UUID | None
    id_destinatario: UUID | None
    fecha_hora: datetime
