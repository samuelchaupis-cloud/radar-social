import hashlib
import unicodedata
from decimal import Decimal
from enum import StrEnum
from typing import Any, Literal

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)


class RedFlagCode(StrEnum):
    PLAZO_EXPRES = "PLAZO_EXPRES"
    FRACCIONAMIENTO_SOSPECHOSO = "FRACCIONAMIENTO_SOSPECHOSO"
    MONTO_ANOMALO = "MONTO_ANOMALO"


def normalize_string(v: str) -> str:
    if not isinstance(v, str):
        return v
    v = v.replace("\x00", "")
    v = unicodedata.normalize("NFC", v)
    return v.strip().lower()


class LicitacionBase(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    titulo: str = Field(min_length=5, max_length=255)
    descripcion: str = Field(max_length=10000)
    url_fuente: HttpUrl = Field(max_length=2083)
    fecha_publicacion: AwareDatetime
    fecha_cierre: AwareDatetime
    entidad_compradora: str = Field(min_length=3, max_length=255)
    monto_estimado: Decimal = Field(gt=Decimal("0.00"), decimal_places=2)
    moneda: Literal["PEN", "USD", "EUR"]
    score_riesgo: int = Field(default=0, ge=0, le=100)
    banderas_rojas: list[RedFlagCode] = Field(default_factory=list, max_length=20)

    @field_validator("titulo", "descripcion", "entidad_compradora", mode="before")
    @classmethod
    def sanitize_text(cls, v: Any) -> Any:
        if isinstance(v, str):
            return normalize_string(v)
        return v

    @model_validator(mode="after")
    def validar_orden_fechas(self) -> "LicitacionBase":
        if self.fecha_cierre < self.fecha_publicacion:
            raise ValueError("fecha_cierre no puede ser anterior a fecha_publicacion")
        return self


class LicitacionCreate(LicitacionBase):
    @property
    def hash_id(self) -> str:
        base = f"{self.titulo}|{str(self.url_fuente)}|{str(self.monto_estimado)}"
        return hashlib.sha256(base.encode("utf-8")).hexdigest()


class Licitacion(LicitacionBase):
    hash_id: str = Field(max_length=64)
    created_at: AwareDatetime
