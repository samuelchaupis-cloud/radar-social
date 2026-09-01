from decimal import Decimal

from radar_social.domain.models import LicitacionBase, RedFlagCode

# Umbrales legales y temporales
SEGUNDOS_48_HORAS = 48 * 3600
MONTO_FRACCIONAMIENTO_MIN_PEN = Decimal("39000.00")
MONTO_FRACCIONAMIENTO_MAX_PEN = Decimal("41200.00")
MONTO_ANOMALO_ALTO = Decimal("10000000.00")


def evaluar_riesgo_licitacion(licitacion: LicitacionBase) -> tuple[int, list[RedFlagCode]]:
    score = 0
    banderas: list[RedFlagCode] = []

    # 1. Regla: Plazo exprés (<48 horas entre publicación y cierre)
    diferencia_segundos = (licitacion.fecha_cierre - licitacion.fecha_publicacion).total_seconds()
    if diferencia_segundos < SEGUNDOS_48_HORAS:
        score += 40
        banderas.append(RedFlagCode.PLAZO_EXPRES)

    # 2. Regla: Fraccionamiento sospechoso
    # (PEN cerca al limite de contratacion directa sin concurso)
    if (
        licitacion.moneda == "PEN"
        and MONTO_FRACCIONAMIENTO_MIN_PEN
        <= licitacion.monto_estimado
        <= MONTO_FRACCIONAMIENTO_MAX_PEN
    ):
        score += 50
        banderas.append(RedFlagCode.FRACCIONAMIENTO_SOSPECHOSO)

    # 3. Regla: Monto anómalo / Megaproyecto de alto impacto
    if licitacion.monto_estimado >= MONTO_ANOMALO_ALTO:
        score += 20
        banderas.append(RedFlagCode.MONTO_ANOMALO)

    # Score acotado estrictamente entre 0 y 100
    score_final = min(100, score)
    return score_final, banderas
