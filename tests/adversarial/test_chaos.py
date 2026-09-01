import asyncio
import os
import tempfile
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import HttpUrl, ValidationError

# Base de datos temporal física para pruebas de contención y concurrencia extrema
fd, test_chaos_db = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_chaos_db}"

from radar_social.domain.models import LicitacionCreate, RedFlagCode  # noqa: E402
from radar_social.domain.red_flags import evaluar_riesgo_licitacion  # noqa: E402
from radar_social.etl.ocds import parsear_ocds_package  # noqa: E402
from radar_social.etl.proxy import ProxyCircuitBreaker, ProxyPool  # noqa: E402
from radar_social.infrastructure.database import (  # noqa: E402
    guardar_licitacion,
    init_db,
    obtener_licitaciones,
)
from radar_social.infrastructure.health import verificar_salud_sistema  # noqa: E402


@pytest.fixture(scope="module", autouse=True)
async def setup_chaos_db():
    await init_db()


def test_chaos_fuzzing_valores_numericos_extremos() -> None:
    now = datetime.now(UTC)

    # 1. Monto negativo debe ser rechazado
    with pytest.raises(ValidationError):
        LicitacionCreate(
            titulo="Licitacion Negativa",
            descripcion="Valores invalidos",
            url_fuente=HttpUrl("http://ejemplo.com/lic/neg"),
            fecha_publicacion=now,
            fecha_cierre=now + timedelta(days=5),
            entidad_compradora="Entidad",
            monto_estimado=Decimal("-500.00"),
            moneda="PEN",
        )

    # 2. Monto cero debe ser rechazado (gt=0.00)
    with pytest.raises(ValidationError):
        LicitacionCreate(
            titulo="Licitacion Cero",
            descripcion="Valores invalidos",
            url_fuente=HttpUrl("http://ejemplo.com/lic/cero"),
            fecha_publicacion=now,
            fecha_cierre=now + timedelta(days=5),
            entidad_compradora="Entidad",
            monto_estimado=Decimal("0.00"),
            moneda="PEN",
        )

    # 3. Monto astronómico (Megaproyecto): Debe aceptarse y levantar MONTO_ANOMALO (+20)
    lic_mega = LicitacionCreate(
        titulo="Megaproyecto Aeroportuario Transcontinental",
        descripcion="Infraestructura masiva",
        url_fuente=HttpUrl("http://ejemplo.com/lic/mega"),
        fecha_publicacion=now,
        fecha_cierre=now + timedelta(days=60),
        entidad_compradora="Ministerio de Transportes",
        monto_estimado=Decimal("50000000.00"),
        moneda="USD",
    )
    score, banderas = evaluar_riesgo_licitacion(lic_mega)
    assert score >= 20
    assert RedFlagCode.MONTO_ANOMALO in banderas


def test_chaos_fuzzing_inyecciones_sql_y_caracteres_corruptos() -> None:
    now = datetime.now(UTC)
    payload_sql = "'; DROP TABLE licitacion; -- \x00\x01\x02"

    lic = LicitacionCreate(
        titulo=f"Contratacion segura {payload_sql}",
        descripcion="Intento de inyeccion en descripcion",
        url_fuente=HttpUrl("http://ejemplo.com/lic/sec"),
        fecha_publicacion=now,
        fecha_cierre=now + timedelta(days=10),
        entidad_compradora=f"Gobierno Regional {payload_sql}",
        monto_estimado=Decimal("15000.00"),
        moneda="PEN",
    )

    # Verifica que el byte nulo fue purgado y el texto normalizado
    assert "\x00" not in lic.titulo
    assert "\x00" not in lic.entidad_compradora
    assert "'; drop table licitacion; --" in lic.titulo


@pytest.mark.asyncio
async def test_chaos_concurrencia_50_escrituras_simultaneas() -> None:
    now = datetime.now(UTC)

    async def worker_insercion(indice: int) -> None:
        lic = LicitacionCreate(
            titulo=f"Licitacion Concurrente Lote {indice}",
            descripcion=f"Prueba de estres concurrente indice {indice}",
            url_fuente=HttpUrl(f"http://ejemplo.com/lic/conc/{indice}"),
            fecha_publicacion=now,
            fecha_cierre=now + timedelta(days=15),
            entidad_compradora="Superintendencia de Contrataciones",
            monto_estimado=Decimal(f"{1000 + indice}.50"),
            moneda="PEN",
        )
        await guardar_licitacion(lic)

    # Disparar 50 tareas concurrentes en paralelo atacando SQLite
    tareas = [worker_insercion(i) for i in range(50)]
    resultados = await asyncio.gather(*tareas, return_exceptions=True)

    # Ninguna corrutina debe haber fallado con SQLITE_BUSY ni OperationalError
    for r in resultados:
        assert not isinstance(r, Exception), f"Fallo concurrente detectado: {r}"

    # Validar que se persistieron todas
    licitaciones = await obtener_licitaciones()
    assert len(licitaciones) >= 50


def test_chaos_ocds_json_bomb_y_anidamiento_extremo() -> None:
    # Simula un paquete OCDS corrupto con 10,000 llaves basura y objetos anidados
    payload_corrupto = {
        "releases": [
            {"tender": {"title": "Release Malicioso", "inyeccion": {"a": {"b": {"c": "boom"}}}}},
            {"basura": "X" * 10000},
            *[{"id": f"release_{i}", "tag": ["tag"]} for i in range(1000)],
        ]
    }
    # No debe colapsar por OOM ni recursion limit
    resultado = parsear_ocds_package(payload_corrupto)
    assert isinstance(resultado, list)
    assert len(resultado) == 0


@pytest.mark.asyncio
async def test_chaos_proxy_pool_concurrente_50_workers() -> None:
    cb = ProxyCircuitBreaker(cooldown_seconds=10.0)
    pool = ProxyPool(
        proxies=[f"http://proxy_{i}.net:8080" for i in range(10)],
        circuit_breaker=cb,
    )

    async def worker_proxy(idx: int) -> None:
        p = await pool.get_proxy()
        await asyncio.sleep(0.01)
        await pool.devolver_proxy(p)

    tareas = [worker_proxy(i) for i in range(50)]
    resultados = await asyncio.gather(*tareas, return_exceptions=True)

    for r in resultados:
        assert not isinstance(r, Exception), f"Error de concurrencia en pool: {r}"


@pytest.mark.asyncio
async def test_chaos_healthcheck_spam_50_llamadas_concurrentes() -> None:
    # 50 llamadas simultáneas a healthcheck para probar la caché TTL y evitar saturación DB
    tareas = [verificar_salud_sistema() for _ in range(50)]
    resultados = await asyncio.gather(*tareas, return_exceptions=True)

    for r in resultados:
        assert isinstance(r, dict)
        assert r["status"] == "HEALTHY"
