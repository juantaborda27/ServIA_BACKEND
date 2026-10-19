from uuid import UUID
from pydantic import BaseModel, Field


class ConversacionResponse(BaseModel):
    id_conversacion: UUID
    id_postulacion: UUID
    estado: str

class ConversacionUpdate(BaseModel):
    estado: str = Field(..., min_length=1, max_length=20)