import asyncio

import structlog

from radar_social.etl.crawler import run_crawler
from radar_social.etl.outbox import OutboxDispatcher

logger = structlog.get_logger(__name__)


async def crawler_daemon(urls: list[str], interval: int, shutdown_event: asyncio.Event) -> None:
    logger.info("Starting crawler daemon", interval=interval)
    while not shutdown_event.is_set():
        try:
            logger.info("Crawler waking up")
            await run_crawler(urls)
            logger.info("Crawler finished, sleeping", interval=interval)

            # Sleep until interval expires OR shutdown is requested
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=interval)
            except TimeoutError:
                pass  # Timeout means we should run again
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Crawler daemon encountered error", error=str(e))
            # Sleep a bit before retrying on error
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=60)
            except TimeoutError:
                pass
    logger.info("Crawler daemon stopped")


async def outbox_daemon(token: str, chat_id: str, shutdown_event: asyncio.Event) -> None:
    logger.info("Starting outbox daemon")
    dispatcher = OutboxDispatcher(token=token, chat_id=chat_id)
    await dispatcher.start()

    await shutdown_event.wait()

    await dispatcher.stop()
    logger.info("Outbox daemon stopped")
