import asyncio
import logging

from app.core.database import AsyncSessionLocal
from app.repositories.conversacion_repository import ConversacionRepository
from app.services.conversacion_service import ConversacionService

logging.basicConfig(level=logging.INFO)


async def run_cleanup() -> dict:
    async with AsyncSessionLocal() as db:
        service = ConversacionService(ConversacionRepository(db))
        return await service.limpiar_conversaciones_expiradas()


if __name__ == "__main__":
    result = asyncio.run(run_cleanup())
    print(result)
