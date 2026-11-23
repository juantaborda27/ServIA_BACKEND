from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.categoria import Categoria

router = APIRouter(
    prefix="/categorias",
    tags=["Categorias"],
)


@router.get("")
async def list_categorias(db: AsyncSession = Depends(get_db)):
    stmt = select(Categoria).order_by(Categoria.nombre.asc())
    categorias = list((await db.execute(stmt)).scalars().all())
    return {
        "items": [
            {
                "id": str(cat.id),
                "nombre": cat.nombre,
                "descripcion": cat.descripcion,
                "icono": cat.icono or "construct-outline",
            }
            for cat in categorias
        ]
    }
