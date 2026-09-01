import asyncio
import time
from typing import Any

from sqlalchemy import func, select

from radar_social.infrastructure.database import AsyncSessionLocal, OutboxEventModel

_CACHED_HEALTH: dict[str, Any] | None = None
_LAST_CHECK_TIME: float = 0.0
_CACHE_TTL: float = 5.0
_LOCK = asyncio.Lock()


async def verificar_salud_sistema(force: bool = False) -> dict[str, Any]:
    global _CACHED_HEALTH, _LAST_CHECK_TIME

    now = time.monotonic()
    if not force and _CACHED_HEALTH is not None and (now - _LAST_CHECK_TIME < _CACHE_TTL):
        return {**_CACHED_HEALTH, "cached": True}

    async with _LOCK:
        now = time.monotonic()
        if not force and _CACHED_HEALTH is not None and (now - _LAST_CHECK_TIME < _CACHE_TTL):
            return {**_CACHED_HEALTH, "cached": True}

        async def _chequear_db() -> dict[str, Any]:
            async with AsyncSessionLocal() as session:
                stmt = select(func.count(OutboxEventModel.id)).where(
                    OutboxEventModel.status == "PENDING"
                )
                result = await session.execute(stmt)
                count = result.scalar() or 0

                return {
                    "status": "HEALTHY",
                    "database": "CONNECTED",
                    "outbox_pending_count": count,
                    "timestamp_monotonic": now,
                }

        try:
            # Timeout acotado estricto a 2.0s para evitar inanicion o DoS en healthchecks
            estado = await asyncio.wait_for(_chequear_db(), timeout=2.0)
        except Exception as e:
            estado = {
                "status": "UNHEALTHY",
                "database": "ERROR",
                "error": str(e),
                "outbox_pending_count": -1,
                "timestamp_monotonic": now,
            }

        _CACHED_HEALTH = estado
        _LAST_CHECK_TIME = now
        return {**estado, "cached": False}
