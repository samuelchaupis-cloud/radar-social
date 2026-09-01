import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Literal

from pydantic import HttpUrl
from selectolax.parser import HTMLParser

from radar_social.domain.models import LicitacionCreate


def parsear_licitacion(html: str) -> LicitacionCreate:
    tree = HTMLParser(html)
    titulo_node = tree.css_first(".titulo")
    desc_node = tree.css_first(".desc")
    fecha_node = tree.css_first(".fecha")
    enlace_node = tree.css_first(".enlace")
    monto_node = tree.css_first(".monto")
    moneda_node = tree.css_first(".moneda")
    entidad_node = tree.css_first(".entidad")
    cierre_node = tree.css_first(".fecha_cierre")

    if not all([titulo_node, desc_node, fecha_node, enlace_node]):
        raise ValueError("HTML malformado o elementos faltantes")

    titulo = titulo_node.text(strip=True) if titulo_node else ""
    desc = desc_node.text(strip=True) if desc_node else ""
    fecha_str = fecha_node.text(strip=True) if fecha_node else ""
    url = enlace_node.attributes.get("href", "") if enlace_node else ""

    if not url:
        raise ValueError("URL no encontrada en el enlace")

    fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))

    # Campos financieros y temporales
    monto_str = monto_node.text(strip=True) if monto_node else "1000.00"
    monto = Decimal(monto_str)

    moneda_raw = moneda_node.text(strip=True).upper() if moneda_node else "PEN"
    moneda_val: Literal["PEN", "USD", "EUR"]
    if moneda_raw == "USD":
        moneda_val = "USD"
    elif moneda_raw == "EUR":
        moneda_val = "EUR"
    else:
        moneda_val = "PEN"

    entidad = entidad_node.text(strip=True) if entidad_node else "Entidad Publica General"

    if cierre_node:
        fecha_cierre = datetime.fromisoformat(cierre_node.text(strip=True).replace("Z", "+00:00"))
    else:
        fecha_cierre = fecha + timedelta(days=7)

    return LicitacionCreate(
        titulo=titulo,
        descripcion=desc,
        url_fuente=HttpUrl(url),
        fecha_publicacion=fecha,
        fecha_cierre=fecha_cierre,
        entidad_compradora=entidad,
        monto_estimado=monto,
        moneda=moneda_val,
    )


async def parsear_licitacion_async(html: str) -> LicitacionCreate:
    return await asyncio.to_thread(parsear_licitacion, html)
