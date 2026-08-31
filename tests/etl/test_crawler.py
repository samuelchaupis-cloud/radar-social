import asyncio
from unittest.mock import patch

import pytest

from radar_social.etl.crawler import run_crawler


@pytest.mark.asyncio
async def test_crawler_backpressure():
    urls = [f"http://test.com/{i}" for i in range(50)]

    processed = []

    async def mock_process(url):
        processed.append(url)
        await asyncio.sleep(0.01)

    with patch("radar_social.etl.crawler.process_url", side_effect=mock_process):
        await run_crawler(urls, concurrency=5, max_queue_size=5)

    assert len(processed) == 50
