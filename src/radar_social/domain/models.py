from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from datetime import datetime


class LicitacionBase(BaseModel):
    model_config = ConfigDict(strict=True)
    titulo: str = Field(min_length=5)
    descripcion: str
    url_fuente: HttpUrl
    fecha_publicacion: datetime


class LicitacionCreate(LicitacionBase):
    pass


class Licitacion(LicitacionBase):
    hash_id: str
    created_at: datetime
