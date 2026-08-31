import asyncio

import structlog
from sqlalchemy import select, update
from tenacity import (
    AsyncRetrying,
    stop_after_attempt,
    wait_random_exponential,
)

from radar_social.infrastructure.database import AsyncSessionLocal, OutboxEventModel

logger = structlog.get_logger(__name__)

MAX_BATCH_SIZE = 20
SLEEP_NO_MESSAGES = 2.0
RATE_LIMIT_WAIT = 60.0


class OutboxDispatcher:
    def __init__(self, token: str, chat_id: str) -> None:
        self.token = token
        self.chat_id = chat_id
        self._running = False
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        logger.info("Outbox dispatcher started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Outbox dispatcher stopped")

    async def _loop(self) -> None:
        while self._running:
            try:
                processed = await self._process_batch()
                if processed == 0:
                    await asyncio.sleep(SLEEP_NO_MESSAGES)
                else:
                    await asyncio.sleep(RATE_LIMIT_WAIT)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Error in outbox loop", error=str(e))
                await asyncio.sleep(5.0)

    async def _process_batch(self) -> int:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                subq = (
                    select(OutboxEventModel.id)
                    .where(OutboxEventModel.status == "PENDING")
                    .limit(MAX_BATCH_SIZE)
                )

                stmt = (
                    update(OutboxEventModel)
                    .where(OutboxEventModel.id.in_(subq))
                    .values(status="PROCESSING")
                    .returning(OutboxEventModel.id)
                )
                result = await session.execute(stmt)
                ids = list(result.scalars().all())

                if not ids:
                    return 0

                logger.info("Batch locked for processing", count=len(ids), ids=ids)

        processed_count = 0
        for msg_id in ids:
            try:
                await self._send_message(msg_id)
                await self._update_status(msg_id, "SENT")
                processed_count += 1
            except Exception as e:
                logger.error("Failed to send message", msg_id=msg_id, error=str(e))
                await self._update_status(msg_id, "FAILED")

        return processed_count

    async def _send_message(self, msg_id: int) -> None:
        async with AsyncSessionLocal() as session:
            stmt = select(OutboxEventModel.payload).where(OutboxEventModel.id == msg_id)
            result = await session.execute(stmt)
            payload = result.scalar_one_or_none()

        if not isinstance(payload, dict):
            return

        url = f"https://api.telegram.org/bot{self.token}/sendMessage"
        text = f"Nueva Licitación:\n{payload.get('titulo')}\n{payload.get('url_fuente')}"
        data = {"chat_id": self.chat_id, "text": text}

        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_random_exponential(multiplier=1, min=2, max=10),
            reraise=True,
        ):
            with attempt:
                await self._http_post(url, data)

    async def _http_post(self, url: str, data: dict[str, str]) -> None:
        from curl_cffi.requests import AsyncSession

        async with AsyncSession() as session:
            response = await session.post(url, json=data, timeout=10)
            if response.status_code == 429:
                raise Exception("Rate limited by Telegram")
            response.raise_for_status()

    async def _update_status(self, msg_id: int, status: str) -> None:
        async with AsyncSessionLocal() as session:
            async with session.begin():
                stmt = (
                    update(OutboxEventModel)
                    .where(OutboxEventModel.id == msg_id)
                    .values(status=status)
                )
                await session.execute(stmt)
