import hashlib
import unicodedata
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator


def normalize_string(v: str) -> str:
    if not isinstance(v, str):
        return v
    v = v.replace("\x00", "")
    v = unicodedata.normalize("NFC", v)
    return v.strip().lower()


class LicitacionBase(BaseModel):
    model_config = ConfigDict(strict=True)
    titulo: str = Field(min_length=5, max_length=255)
    descripcion: str = Field(max_length=10000)
    url_fuente: HttpUrl = Field(max_length=2083)
    fecha_publicacion: datetime

    @field_validator("titulo", "descripcion", mode="before")
    @classmethod
    def sanitize_text(cls, v: Any) -> Any:
        if isinstance(v, str):
            return normalize_string(v)
        return v


class LicitacionCreate(LicitacionBase):
    @property
    def hash_id(self) -> str:
        base = f"{self.titulo}|{str(self.url_fuente)}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()


class Licitacion(LicitacionBase):
    hash_id: str = Field(max_length=64)
    created_at: datetime
