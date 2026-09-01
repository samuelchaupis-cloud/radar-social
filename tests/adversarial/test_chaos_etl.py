import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest
from curl_cffi.requests.errors import RequestsError
from pydantic import HttpUrl, ValidationError

from radar_social.domain.models import LicitacionCreate
from radar_social.etl.extract import extraer_html_resiliente
from radar_social.etl.transform import parsear_licitacion


def test_chaos_licitacion_extra_forbid() -> None:
    # Debe fallar si se inyectan campos extra, previniendo fuga de memoria
    dt = datetime.now(UTC)
    with pytest.raises(ValidationError) as exc_info:
        LicitacionCreate(
            titulo="licitacion normal",
            descripcion="desc",
            url_fuente=HttpUrl("http://ejemplo.com"),
            fecha_publicacion=dt,
            fecha_cierre=dt + timedelta(days=5),
            entidad_compradora="Entidad",
            monto_estimado=Decimal("1000.00"),
            moneda="PEN",
            payload_malicioso="A" * 10000,
        )
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_chaos_html_profundamente_anidado() -> None:
    # Simula HTML corrupto o bomba de profundidad (Zip Bomb style)
    # selectolax en C maneja esto muy rpido, pero verificamos que falle gracilmente
    html = "<div>" * 5000 + "texto" + "</div>" * 5000
    with pytest.raises(ValueError, match="HTML malformado o elementos faltantes"):
        parsear_licitacion(html)


@pytest.mark.asyncio
async def test_chaos_massive_http_timeouts() -> None:
    # Simulamos 50 llamadas concurrentes que se agotan por timeout
    # curl_cffi levanta RequestsError. Verificamos que tenacity limite a 5 reintentos
    # y finalmente levante el error, sin bloquear el event loop.

    mock_get = AsyncMock()
    mock_get.side_effect = RequestsError("Timeout simulated")

    with patch("radar_social.etl.extract.AsyncSession.get", mock_get):
        urls = [f"http://timeout.com/{i}" for i in range(50)]

        # Al ejecutarse concurrente, todas deberan fallar y lanzar excepcion
        resultados = await asyncio.gather(
            *[extraer_html_resiliente(url) for url in urls], return_exceptions=True
        )

        assert len(resultados) == 50
        for res in resultados:
            # tenacity engloba el \u00faltimo error en RetryError o levanta el mismo
            assert isinstance(res, Exception)

        # Fueron 50 urls, cada una reintenta 5 veces (intento inicial + 4 retries)
        # por stop_after_attempt(5) = 5 attempts per URL -> 250 calls
        assert mock_get.call_count == 250
