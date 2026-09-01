from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import HttpUrl, ValidationError

from radar_social.domain.models import LicitacionCreate, RedFlagCode
from radar_social.domain.red_flags import evaluar_riesgo_licitacion


def test_rechazo_estricto_float_en_monto() -> None:
    now = datetime.now(UTC)
    # Prohibido usar float: debe fallar con ValidationError
    with pytest.raises(ValidationError):
        LicitacionCreate.model_validate(
            {
                "titulo": "Licitacion de prueba",
                "descripcion": "Descripcion formal",
                "url_fuente": "https://contrataciones.gob.pe/lic/1",
                "fecha_publicacion": now,
                "fecha_cierre": now + timedelta(days=5),
                "entidad_compradora": "Ministerio de Salud",
                "monto_estimado": 40500.50,  # float no permitido
                "moneda": "PEN",
            }
        )


def test_rechazo_fechas_inconsistentes() -> None:
    now = datetime.now(UTC)
    # Fecha de cierre anterior a la fecha de publicacion
    with pytest.raises(ValidationError):
        LicitacionCreate(
            titulo="Licitacion temporalmente invalida",
            descripcion="Descripcion formal",
            url_fuente=HttpUrl("https://contrataciones.gob.pe/lic/2"),
            fecha_publicacion=now,
            fecha_cierre=now - timedelta(hours=1),
            entidad_compradora="Municipalidad Metropolitana",
            monto_estimado=Decimal("50000.00"),
            moneda="PEN",
        )


def test_motor_red_flags_plazo_expres_y_fraccionamiento() -> None:
    now = datetime.now(UTC)
    # Plazo exprés (<48h) + Fraccionamiento (40,000 PEN)
    lic = LicitacionCreate(
        titulo="Adquisicion de suministros de computo",
        descripcion="Compra directa de laptops para oficina",
        url_fuente=HttpUrl("https://contrataciones.gob.pe/lic/3"),
        fecha_publicacion=now,
        fecha_cierre=now + timedelta(hours=24),  # < 48h -> PLAZO_EXPRES (+40)
        entidad_compradora="Gobierno Regional",
        monto_estimado=Decimal("40000.00"),  # Entre 39,000 y 41,200 PEN -> FRACCIONAMIENTO (+50)
        moneda="PEN",
    )

    score, banderas = evaluar_riesgo_licitacion(lic)

    assert score == 90
    assert RedFlagCode.PLAZO_EXPRES in banderas
    assert RedFlagCode.FRACCIONAMIENTO_SOSPECHOSO in banderas


def test_motor_red_flags_licitacion_limpia() -> None:
    now = datetime.now(UTC)
    lic = LicitacionCreate(
        titulo="Construccion de puente vehicular bicentenario",
        descripcion="Obra publica regular con convocatoria extendida",
        url_fuente=HttpUrl("https://contrataciones.gob.pe/lic/4"),
        fecha_publicacion=now,
        fecha_cierre=now + timedelta(days=30),
        entidad_compradora="Ministerio de Transportes",
        monto_estimado=Decimal("2500000.00"),
        moneda="PEN",
    )

    score, banderas = evaluar_riesgo_licitacion(lic)

    assert score == 0
    assert len(banderas) == 0
