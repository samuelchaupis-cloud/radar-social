import os
import tempfile
from datetime import UTC, datetime

import pytest
from pydantic import HttpUrl

# Creamos un DB temporal real para evitar problemas con in-memory y threading
fd, test_db_path = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_path}"

from radar_social.domain.models import LicitacionCreate  # noqa: E402
from radar_social.infrastructure.database import (  # noqa: E402
    AsyncSessionLocal,
    LicitacionModel,
    OutboxEventModel,
    guardar_licitacion,
    init_db,
    obtener_eventos_outbox,
    obtener_licitaciones,
)


@pytest.fixture(autouse=True)
async def setup_teardown():
    await init_db()
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(LicitacionModel.__table__.delete())
            await session.execute(OutboxEventModel.__table__.delete())
    yield


@pytest.mark.asyncio
async def test_guardar_licitacion_transaccional() -> None:
    lic = LicitacionCreate(
        titulo="Licitacion Prueba",
        descripcion="Desc",
        url_fuente=HttpUrl("http://ejemplo.com"),
        fecha_publicacion=datetime.now(UTC),
    )

    await guardar_licitacion(lic)

    licitaciones = await obtener_licitaciones()
    assert len(licitaciones) == 1
    assert licitaciones[0].titulo == "licitacion prueba"

    eventos = await obtener_eventos_outbox()
    assert len(eventos) == 1
    assert eventos[0].event_type == "TELEGRAM_ALERT"
