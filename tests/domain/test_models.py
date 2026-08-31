from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from radar_social.domain.models import LicitacionCreate


def test_licitacion_create_validacion_estricta() -> None:
    # Falla intencionalmente por tipos incorrectos
    with pytest.raises(ValidationError):
        LicitacionCreate(
            titulo=123,
            descripcion="Descripción válida",
            url_fuente="http://ejemplo.com",
            fecha_publicacion="no-una-fecha",
        )

    # Éxito con datos correctos
    dt = datetime.now(UTC)
    lic = LicitacionCreate(
        titulo="Licitacion 1",
        descripcion="Desc",
        url_fuente="http://ejemplo.com",
        fecha_publicacion=dt,
    )
    assert lic.titulo == "Licitacion 1"
