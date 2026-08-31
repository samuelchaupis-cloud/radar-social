from datetime import UTC, datetime

import pytest

from radar_social.etl.transform import parsear_licitacion, parsear_licitacion_async


def test_parsear_licitacion_valida() -> None:
    html = """
    <div class="licitacion">
        <h1 class="titulo">Construcción de Escuela</h1>
        <p class="desc">Detalles del proyecto de obra</p>
        <span class="fecha">2026-08-31T10:00:00Z</span>
        <a class="enlace" href="http://ejemplo.com/lic/1">Enlace</a>
    </div>
    """
    resultado = parsear_licitacion(html)
    assert resultado.titulo == "construcción de escuela"
    assert resultado.descripcion == "detalles del proyecto de obra"
    assert str(resultado.url_fuente) == "http://ejemplo.com/lic/1"
    assert resultado.fecha_publicacion == datetime(2026, 8, 31, 10, 0, 0, tzinfo=UTC)


def test_parsear_licitacion_incompleta() -> None:
    html = '<div class="licitacion"><h1 class="titulo">Incompleto</h1></div>'
    with pytest.raises(ValueError):
        parsear_licitacion(html)


def test_parsear_licitacion_sin_url() -> None:
    html = """
    <div class="licitacion">
        <h1 class="titulo">Construcción de Escuela</h1>
        <p class="desc">Detalles del proyecto de obra</p>
        <span class="fecha">2026-08-31T10:00:00Z</span>
        <a class="enlace">Enlace sin href</a>
    </div>
    """
    with pytest.raises(ValueError, match="URL no encontrada en el enlace"):
        parsear_licitacion(html)


@pytest.mark.asyncio
async def test_parsear_licitacion_async_valida() -> None:
    html = """
    <div class="licitacion">
        <h1 class="titulo">Construcción de Escuela async</h1>
        <p class="desc">Detalles</p>
        <span class="fecha">2026-08-31T10:00:00Z</span>
        <a class="enlace" href="http://ejemplo.com/lic/2">Enlace</a>
    </div>
    """
    resultado = await parsear_licitacion_async(html)
    assert resultado.titulo == "construcción de escuela async"
