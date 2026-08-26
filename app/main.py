from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth
from app.routers import usuario
from app.routers import servicios
from app.routers import post
from app.routers import prestador
from app.routers import postulacion
app = FastAPI(
    title="DataBaseServIA API",
    description="API para plataforma de servicios de Valledupar",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], 
    allow_credentials=True,
    allow_methods=["*"], 
    allow_headers=["*"], 
)

app.include_router(auth.router)
app.include_router(usuario.router)
app.include_router(servicios.router)
app.include_router(post.router)
app.include_router(prestador.router)
app.include_router(postulacion.router)
# 4. Ruta raíz
@app.get("/")
def root():
    return {
        "message": "Bienvenido a la API de DataBaseServIA",
    }