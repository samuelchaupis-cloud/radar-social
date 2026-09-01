import os
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import HttpUrl
from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError

# Creamos un DB temporal real para evitar problemas con in-memory y threading
fd, test_db_path = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_path}"

from radar_social.domain.models import LicitacionCreate  # noqa: E402
from radar_social.infrastructure.database import (  # noqa: E402
    AsyncSessionLocal,
    Base,
    LicitacionModel,
    engine,
    guardar_licitacion,
    init_db,
    obtener_eventos_outbox,
    obtener_licitaciones,
)


@pytest.fixture(autouse=True)
async def setup_teardown():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()
    yield


@pytest.mark.asyncio
async def test_guardar_licitacion_transaccional() -> None:
    now = datetime.now(UTC)
    lic = LicitacionCreate(
        titulo="Licitacion Prueba Transaccional",
        descripcion="Descripcion completa para prueba",
        url_fuente=HttpUrl("http://ejemplo.com/lic/test"),
        fecha_publicacion=now,
        fecha_cierre=now + timedelta(hours=20),  # <48h -> Activa PLAZO_EXPRES (+40)
        entidad_compradora="Ministerio de Salud",
        monto_estimado=Decimal("40000.00"),  # Activa FRACCIONAMIENTO (+50)
        moneda="PEN",
    )

    await guardar_licitacion(lic)

    licitaciones = await obtener_licitaciones()
    assert len(licitaciones) == 1
    assert licitaciones[0].titulo == "licitacion prueba transaccional"
    assert licitaciones[0].score_riesgo == 90
    assert "PLAZO_EXPRES" in licitaciones[0].banderas_rojas
    assert "FRACCIONAMIENTO_SOSPECHOSO" in licitaciones[0].banderas_rojas
    assert licitaciones[0].monto_estimado == "40000.00"

    eventos = await obtener_eventos_outbox()
    assert len(eventos) == 1
    assert eventos[0].event_type == "TELEGRAM_ALERT"
    assert eventos[0].payload["score_riesgo"] == 90


@pytest.mark.asyncio
async def test_inmutabilidad_trigger_prevent_update() -> None:
    now = datetime.now(UTC)
    lic = LicitacionCreate(
        titulo="Licitacion Inmutable",
        descripcion="Desc",
        url_fuente=HttpUrl("http://ejemplo.com/inmutable"),
        fecha_publicacion=now,
        fecha_cierre=now + timedelta(days=5),
        entidad_compradora="Entidad Publica",
        monto_estimado=Decimal("5000.00"),
        moneda="PEN",
    )
    await guardar_licitacion(lic)

    # Intento de UPDATE debe ser abortado por el Trigger
    with pytest.raises(IntegrityError, match="Inmutabilidad violada"):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = (
                    update(LicitacionModel)
                    .where(LicitacionModel.hash_id == lic.hash_id)
                    .values(titulo="mutado")
                )
                await session.execute(stmt)


@pytest.mark.asyncio
async def test_inmutabilidad_trigger_prevent_delete() -> None:
    now = datetime.now(UTC)
    lic = LicitacionCreate(
        titulo="Licitacion Inmutable Borrado",
        descripcion="Desc",
        url_fuente=HttpUrl("http://ejemplo.com/inmutable_del"),
        fecha_publicacion=now,
        fecha_cierre=now + timedelta(days=5),
        entidad_compradora="Entidad Publica",
        monto_estimado=Decimal("5000.00"),
        moneda="PEN",
    )
    await guardar_licitacion(lic)

    # Intento de DELETE debe ser abortado por el Trigger
    with pytest.raises(IntegrityError, match="Inmutabilidad violada"):
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = delete(LicitacionModel).where(LicitacionModel.hash_id == lic.hash_id)
                await session.execute(stmt)
