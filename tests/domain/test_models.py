from datetime import UTC, datetime

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
    )
    # Verifica normalización (strip, lowercase, no nulos)
    assert lic.titulo == "licitacion 1"

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
        )
