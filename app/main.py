from fastapi import FastAPI

from app.routers import auth

app = FastAPI(
    title="DataBaseServIA API",
    description="API para plataforma de servicios de Valledupar",
    version="1.0.0"
)

app.include_router(auth.router)

@app.get("/")
def root():
    return {
        "message": "Bienvenido a la API de DataBaseServIA",
    }