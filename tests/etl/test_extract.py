import pytest
from pytest_httpx import HTTPXMock

from radar_social.etl.extract import extraer_html_resiliente


@pytest.mark.asyncio
async def test_extraer_html_resiliente_exito(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url="http://ejemplo.com", text="<html>OK</html>")
    resultado = await extraer_html_resiliente("http://ejemplo.com")
    assert resultado == "<html>OK</html>"
