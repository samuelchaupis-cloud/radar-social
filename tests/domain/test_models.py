from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import HttpUrl, ValidationError

from radar_social.domain.models import LicitacionCreate


def test_licitacion_create_validacion_estricta() -> None:
    # Falla intencionalmente por tipos incorrectos
    with pytest.raises(ValidationError):
        LicitacionCreate.model_validate(
            {
                "titulo": 123,
                "descripcion": "Descripción válida",
                "url_fuente": "http://ejemplo.com",
                "fecha_publicacion": "no-una-fecha",
            }
        )

    # Éxito con datos correctos
    dt = datetime.now(UTC)
    lic = LicitacionCreate(
        titulo=" Licitacion 1  \x00 ",
        descripcion="Desc",
        url_fuente=HttpUrl("http://ejemplo.com"),
        fecha_publicacion=dt,
        fecha_cierre=dt + timedelta(days=5),
        entidad_compradora="Municipalidad Metropolitana",
        monto_estimado=Decimal("15000.00"),
        moneda="PEN",
    )
    # Verifica normalización (strip, lowercase, no nulos)
    assert lic.titulo == "licitacion 1"
    assert lic.entidad_compradora == "municipalidad metropolitana"

    # Verifica generación de hash
    assert isinstance(lic.hash_id, str)
    assert len(lic.hash_id) == 64


def test_licitacion_max_length() -> None:
    dt = datetime.now(UTC)
    with pytest.raises(ValidationError):
        LicitacionCreate(
            titulo="a" * 256,
            descripcion="Desc",
            url_fuente=HttpUrl("http://ejemplo.com"),
            fecha_publicacion=dt,
            fecha_cierre=dt + timedelta(days=5),
            entidad_compradora="Entidad",
            monto_estimado=Decimal("1000.00"),
            moneda="PEN",
        )
