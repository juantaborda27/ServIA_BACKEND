from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth
from app.routers import usuario
from app.routers import servicios
from app.routers import post
from app.routers import prestador
from app.routers import postulacion
<<<<<<< HEAD
from app.routers import chat
from app.routers import conversacion
from app.core.database import engine, Base
from app import models
from contextlib import asynccontextmanager
#from app.core.database_function import crear_funciones

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        #await crear_funciones(conn)
    yield


=======
from app.routers import resenas
from app.routers import notificacion
from app.routers import health
>>>>>>> 610bbb7 (reseñas e historial de trabajo)
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
    allow_methods=["*"], 
    allow_headers=["*"], 
)

app.include_router(auth.router)
app.include_router(usuario.router)
app.include_router(servicios.router)
app.include_router(post.router)
app.include_router(prestador.router)
app.include_router(postulacion.router)
<<<<<<< HEAD
app.include_router(chat.router)
app.include_router(conversacion.router)
=======
app.include_router(resenas.router)
app.include_router(notificacion.router)
app.include_router(health.router)
>>>>>>> 610bbb7 (reseñas e historial de trabajo)
# 4. Ruta raíz
@app.get("/")
def root():
    return {
        "message": "Bienvenido a la API de DataBaseServIA",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}