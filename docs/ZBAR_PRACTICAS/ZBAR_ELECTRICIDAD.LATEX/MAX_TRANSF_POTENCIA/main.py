# main.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import Optional

# 1. Se crea una instancia de FastAPI
app = FastAPI()

# 2. Se define un modelo de datos con Pydantic
#    Esto proporciona validación automática de tipos.
class Item(BaseModel):
    name: str
    description: Optional[str] = None
    price: float
    tax: Optional[float] = None

# 3. Se crea una "operación de ruta" (route) con un decorador
#    @app.get("/") define una ruta para peticiones GET a la raíz.
@app.get("/")
def read_root():
    return {"Hello": "World"}

# Ruta con un parámetro de ruta
# El valor de {item_id} se pasará como argumento a la función.
@app.get("/items/{item_id}")
def read_item(item_id: int, q: Optional[str] = None):
    # FastAPI valida que item_id sea un entero.
    # q es un parámetro de consulta opcional.
    return {"item_id": item_id, "q": q}

# Ruta que recibe un cuerpo de petición (request body)
# FastAPI usará el modelo 'Item' para validar, convertir y documentar
# el JSON que se reciba en la petición.
@app.post("/items/")
def create_item(item: Item):
    return item
