from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import HttpUrl, ValidationError

from radar_social.domain.models import LicitacionCreate


def parsear_ocds_package(data: dict[str, Any]) -> list[LicitacionCreate]:
    releases = data.get("releases", [])
    if not isinstance(releases, list):
        return []

    licitaciones: list[LicitacionCreate] = []

    for rel in releases:
        if not isinstance(rel, dict):
            continue

        tender = rel.get("tender")
        if not isinstance(tender, dict):
            continue

        titulo = tender.get("title")
        desc = tender.get("description", "Sin descripcion")
        if not titulo or not isinstance(titulo, str):
            continue

        # Validacion defensiva del valor y monto
        value_data = tender.get("value")
        if not isinstance(value_data, dict):
            continue

        amount_raw = value_data.get("amount")
        if amount_raw is None:
            continue

        try:
            monto = Decimal(str(amount_raw))
            if monto <= Decimal("0.00"):
                continue
        except (InvalidOperation, TypeError, ValueError):
            continue

        currency_raw = str(value_data.get("currency", "PEN")).upper()
        moneda: Literal["PEN", "USD", "EUR"]
        if currency_raw == "USD":
            moneda = "USD"
        elif currency_raw == "EUR":
            moneda = "EUR"
        else:
            moneda = "PEN"

        # Entidad compradora
        entity_data = tender.get("procuringEntity", {})
        entidad = "Entidad Publica"
        if isinstance(entity_data, dict) and "name" in entity_data:
            entidad = str(entity_data["name"])

        # Fechas del periodo de licitacion
        period = tender.get("tenderPeriod", {})
        if not isinstance(period, dict):
            continue

        start_str = period.get("startDate")
        end_str = period.get("endDate")
        if not start_str or not end_str:
            continue

        try:
            fecha_pub = datetime.fromisoformat(str(start_str).replace("Z", "+00:00"))
            fecha_cie = datetime.fromisoformat(str(end_str).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue

        # URL fuente o default OCDS
        url_str = tender.get("url") or f"https://contrataciones.gob.pe/ocds/{rel.get('ocid', '0')}"

        try:
            lic = LicitacionCreate(
                titulo=titulo,
                descripcion=desc if isinstance(desc, str) else "Sin descripcion",
                url_fuente=HttpUrl(url_str),
                fecha_publicacion=fecha_pub,
                fecha_cierre=fecha_cie,
                entidad_compradora=entidad,
                monto_estimado=monto,
                moneda=moneda,
            )
            licitaciones.append(lic)
        except (ValidationError, ValueError):
            # Omitir cualquier release que viole invariantes de dominio
            continue

    return licitaciones
