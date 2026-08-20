from fastapi import FastAPI

app = FastAPI()  # <-- Esta variable DEBE llamarse 'app'

@app.get("/")
def read_root():
    return {"mensaje": "¡ServIA Backend activo!"}