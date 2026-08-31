from datetime import UTC, datetime

import pytest
from pydantic import HttpUrl

from radar_social.domain.models import LicitacionCreate
from radar_social.infrastructure.database import (
    guardar_licitacion,
    init_db,
    obtener_eventos_outbox,
    obtener_licitaciones,
)


@pytest.mark.asyncio
async def test_guardar_licitacion_transaccional() -> None:
    await init_db()

    lic = LicitacionCreate(
        titulo="Licitacion Prueba",
        descripcion="Desc",
        url_fuente=HttpUrl("http://ejemplo.com"),
        fecha_publicacion=datetime.now(UTC),
    )

    await guardar_licitacion(lic)

    licitaciones = await obtener_licitaciones()
    assert len(licitaciones) == 1
    assert licitaciones[0].titulo == "Licitacion Prueba"

    eventos = await obtener_eventos_outbox()
    assert len(eventos) == 1
    assert eventos[0].event_type == "TELEGRAM_ALERT"
