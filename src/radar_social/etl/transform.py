import asyncio
from datetime import datetime

from pydantic import HttpUrl
from selectolax.parser import HTMLParser

from radar_social.domain.models import LicitacionCreate


def parsear_licitacion(html: str) -> LicitacionCreate:
    tree = HTMLParser(html)
    titulo_node = tree.css_first(".titulo")
    desc_node = tree.css_first(".desc")
    fecha_node = tree.css_first(".fecha")
    enlace_node = tree.css_first(".enlace")

    if not all([titulo_node, desc_node, fecha_node, enlace_node]):
        raise ValueError("HTML malformado o elementos faltantes")

    # Los nodos no son nulos en este punto gracias a la validación anterior.
    titulo = titulo_node.text(strip=True) if titulo_node else ""
    desc = desc_node.text(strip=True) if desc_node else ""
    fecha_str = fecha_node.text(strip=True) if fecha_node else ""
    url = enlace_node.attributes.get("href", "") if enlace_node else ""

    if not url:
        raise ValueError("URL no encontrada en el enlace")

    # Aseguramos que la fecha es interpretada con información de zona horaria (UTC)
    fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))

    return LicitacionCreate(
        titulo=titulo, descripcion=desc, url_fuente=HttpUrl(url), fecha_publicacion=fecha
    )


async def parsear_licitacion_async(html: str) -> LicitacionCreate:
    return await asyncio.to_thread(parsear_licitacion, html)
