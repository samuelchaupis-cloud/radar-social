import asyncio
from unittest.mock import patch

import pytest

from radar_social.etl.ocds import parsear_ocds_package
from radar_social.etl.proxy import (
    CircuitBreakerOpenError,
    CircuitState,
    ProxyCircuitBreaker,
    ProxyPool,
    sanitizar_url_proxy,
)
from radar_social.infrastructure.health import verificar_salud_sistema


def test_sanitizar_url_proxy() -> None:
    url_con_credenciales = "http://usuario_secreto:clave_super_secreta@192.168.1.100:8080"
    url_limpia = sanitizar_url_proxy(url_con_credenciales)
    assert "usuario_secreto" not in url_limpia
    assert "clave_super_secreta" not in url_limpia
    assert url_limpia == "http://***:***@192.168.1.100:8080"


def test_parsear_ocds_package_valido() -> None:
    ocds_data = {
        "version": "1.1",
        "releases": [
            {
                "ocid": "ocds-k4xxv2-0001",
                "id": "rel-001",
                "date": "2026-09-01T10:00:00Z",
                "tag": ["tender"],
                "tender": {
                    "id": "tender-001",
                    "title": "Adquisicion de Equipamiento Medico Hospitalario",
                    "description": "Licitacion publica para compra de tomografos",
                    "value": {"amount": "450000.00", "currency": "PEN"},
                    "procuringEntity": {"id": "PE-MINSA", "name": "Ministerio de Salud"},
                    "tenderPeriod": {
                        "startDate": "2026-09-01T10:00:00Z",
                        "endDate": "2026-09-20T18:00:00Z",
                    },
                },
            },
            {
                "ocid": "ocds-k4xxv2-0002",
                "id": "rel-002",
                "tender": {
                    "title": "Adquisicion Internacional EUR",
                    "value": {"amount": 25000, "currency": "EUR"},
                    "tenderPeriod": {
                        "startDate": "2026-09-01T10:00:00Z",
                        "endDate": "2026-09-20T18:00:00Z",
                    },
                },
            },
        ],
    }

    licitaciones = parsear_ocds_package(ocds_data)
    assert len(licitaciones) == 2
    assert licitaciones[0].moneda == "PEN"
    assert licitaciones[1].moneda == "EUR"
    assert licitaciones[1].entidad_compradora == "entidad publica"


def test_parsear_ocds_package_defensivo_omite_invalidos() -> None:
    # Casos bordes: no dict, no list, releases corruptos
    assert parsear_ocds_package({"releases": "no-una-lista"}) == []
    assert parsear_ocds_package({}) == []

    ocds_data = {
        "releases": [
            "no-un-dict",
            {"tender": "no-un-dict"},
            {"tender": {"title": "Incompleto"}},  # Falta valor, fechas, etc.
            {"tender": {"title": "Sin value", "description": "d"}},
            {"tender": {"title": "Value sin amount", "value": {}}},
            {
                "tender": {
                    "title": "Licitacion con Monto Invalido",
                    "description": "Desc",
                    "value": {"amount": "-500.00", "currency": "PEN"},  # Invalido
                    "procuringEntity": {"name": "Entidad"},
                    "tenderPeriod": {
                        "startDate": "2026-09-01T10:00:00Z",
                        "endDate": "2026-09-10T10:00:00Z",
                    },
                }
            },
            {
                "tender": {
                    "title": "Licitacion con fechas corruptas",
                    "value": {"amount": "100.00"},
                    "tenderPeriod": {"startDate": "fecha-invalida", "endDate": "2026-09-10"},
                }
            },
        ]
    }
    licitaciones = parsear_ocds_package(ocds_data)
    assert len(licitaciones) == 0


@pytest.mark.asyncio
async def test_proxy_pool_y_circuit_breaker() -> None:
    cb = ProxyCircuitBreaker(cooldown_seconds=0.1)
    pool = ProxyPool(proxies=["http://proxy1:8080", "http://proxy2:8080"], circuit_breaker=cb)

    # Adquirir proxies
    p1 = await pool.get_proxy()
    assert p1 in ("http://proxy1:8080", "http://proxy2:8080")

    # Devolver proxy
    await pool.devolver_proxy(p1)

    # Penalizar proxies hasta abrir el circuito
    p1 = await pool.get_proxy()
    await pool.penalizar_proxy(p1)
    p2 = await pool.get_proxy()
    await pool.penalizar_proxy(p2)

    assert cb.is_open() is True
    assert cb.state == CircuitState.OPEN

    # Al estar abierto, solicitar proxy debe lanzar CircuitBreakerOpenError
    with pytest.raises(CircuitBreakerOpenError):
        await pool.get_proxy()

    # Esperar que expire el cooldown para entrar en HALF_OPEN
    await asyncio.sleep(0.15)
    assert cb.is_open() is False
    assert cb.state == CircuitState.HALF_OPEN


@pytest.mark.asyncio
async def test_healthcheck_sistema() -> None:
    salud = await verificar_salud_sistema(force=True)
    assert salud["status"] == "HEALTHY"
    assert salud["database"] == "CONNECTED"
    assert "outbox_pending_count" in salud
    assert salud["cached"] is False

    # Segunda llamada usa cache
    salud_cached = await verificar_salud_sistema()
    assert salud_cached["cached"] is True


@pytest.mark.asyncio
async def test_healthcheck_error_de_db() -> None:
    with patch(
        "radar_social.infrastructure.health.AsyncSessionLocal",
        side_effect=Exception("DB caida"),
    ):
        salud = await verificar_salud_sistema(force=True)
        assert salud["status"] == "UNHEALTHY"
        assert salud["database"] == "ERROR"
