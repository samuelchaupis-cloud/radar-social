from unittest.mock import AsyncMock, patch

import pytest
from tenacity.wait import wait_random_exponential

from radar_social.etl.extract import extraer_html_resiliente


def test_extraer_html_usa_jitter() -> None:
    # Verificamos que el backoff usa full jitter para evitar Thundering Herd
    assert isinstance(extraer_html_resiliente.retry.wait, wait_random_exponential)


@pytest.mark.asyncio
@patch("radar_social.etl.extract.AsyncSession.get")
async def test_extraer_html_resiliente_exito(mock_get) -> None:
    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = "<html>OK</html>"
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response

    resultado = await extraer_html_resiliente("http://ejemplo.com")
    assert resultado == "<html>OK</html>"
