from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.routers import auth
from app.routers import usuario
from app.routers import servicios
from app.routers import post
from app.routers import prestador
from app.routers import postulacion
from app.routers import chat
from app.routers import conversacion
from app.routers import resenas
from app.routers import notificacion
from app.routers import categoria
from app.routers import ubicacion
from app.core.database import engine, Base
from app.core.connectionManager import manager_connection
from app.core.seed import seed_categorias
from app import models
from contextlib import asynccontextmanager
#from app.core.database_function import crear_funciones

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        # Evita carreras cuando las dos tareas ECS arrancan al mismo tiempo.
        await conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('servia_schema_init'))"))
        await conn.run_sync(Base.metadata.create_all)
        await seed_categorias(conn)
        #await crear_funciones(conn)
    await manager_connection.start()
    try:
        yield
    finally:
        await manager_connection.stop()
app = FastAPI(
    title="DataBaseServIA API",
    description="API para plataforma de servicios de Valledupar",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    # En desarrollo evitamos conservar políticas preflight antiguas en el navegador.
    max_age=0,
)

app.include_router(auth.router)
app.include_router(usuario.router)
app.include_router(servicios.router)
app.include_router(post.router)
app.include_router(prestador.router)
app.include_router(postulacion.router)
app.include_router(chat.router)
app.include_router(conversacion.router)
app.include_router(resenas.router)
app.include_router(notificacion.router)
app.include_router(categoria.router)
app.include_router(ubicacion.router)
# 4. Ruta raíz
@app.get("/")
def root():
    return {
        "message": "Bienvenido a la API de DataBaseServIA",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}
