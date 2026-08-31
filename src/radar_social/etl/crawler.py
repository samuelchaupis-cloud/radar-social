import asyncio

import structlog

from radar_social.etl.extract import extraer_html_resiliente
from radar_social.etl.transform import parsear_licitacion
from radar_social.infrastructure.database import guardar_licitacion

logger = structlog.get_logger(__name__)


async def process_url(url: str) -> None:
    try:
        html = await extraer_html_resiliente(url)
        lic = parsear_licitacion(html)
        await guardar_licitacion(lic)
        logger.info("URL processed successfully", url=url)
    except Exception as e:
        logger.error("Failed to process URL", url=url, error=str(e))


async def worker(queue: asyncio.Queue[str]) -> None:
    while True:
        try:
            url = await queue.get()
            await process_url(url)
        finally:
            queue.task_done()


async def run_crawler(urls: list[str], concurrency: int = 10, max_queue_size: int = 20) -> None:
    queue: asyncio.Queue[str] = asyncio.Queue(maxsize=max_queue_size)

    workers = [asyncio.create_task(worker(queue)) for _ in range(concurrency)]

    logger.info(
        "Starting crawler",
        concurrency=concurrency,
        max_queue_size=max_queue_size,
        total_urls=len(urls),
    )

    for url in urls:
        await queue.put(url)

    await queue.join()

    for w in workers:
        w.cancel()

    await asyncio.gather(*workers, return_exceptions=True)
    logger.info("Crawler finished")
