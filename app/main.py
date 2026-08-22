from fastapi import FastAPI

from app.routers import auth
from app.routers import usuario

app = FastAPI(
    title="DataBaseServIA API",
    description="API para plataforma de servicios de Valledupar",
    version="1.0.0"
)

app.include_router(auth.router)
app.include_router(usuario.router)

@app.get("/")
def root():
    return {
        "message": "Bienvenido a la API de DataBaseServIA",
    }