import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from radar_social.daemons import crawler_daemon, outbox_daemon


@pytest.mark.asyncio
async def test_crawler_daemon_runs_and_waits():
    shutdown_event = asyncio.Event()

    async def mock_run_crawler(urls):
        # Cuando se ejecute la primera vez, marcamos el shutdown
        shutdown_event.set()

    with patch("radar_social.daemons.run_crawler", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = mock_run_crawler
        await crawler_daemon(urls=["http://test"], interval=1, shutdown_event=shutdown_event)

    mock_run.assert_called_once()


@pytest.mark.asyncio
async def test_crawler_daemon_exception():
    shutdown_event = asyncio.Event()
    call_count = 0

    async def mock_run_crawler(urls):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("Crawler failed")
        else:
            shutdown_event.set()

    with patch("radar_social.daemons.run_crawler", new_callable=AsyncMock) as mock_run:
        mock_run.side_effect = mock_run_crawler
        with patch("asyncio.wait_for") as mock_wait:
            mock_wait.side_effect = [asyncio.TimeoutError, None]
            await crawler_daemon(urls=["http://test"], interval=1, shutdown_event=shutdown_event)

    assert call_count == 2


@pytest.mark.asyncio
async def test_outbox_daemon_flow():
    shutdown_event = asyncio.Event()
    shutdown_event.set()
    with patch("radar_social.daemons.OutboxDispatcher") as mock_outbox:
        mock_instance = mock_outbox.return_value
        mock_instance.start = AsyncMock()
        mock_instance.stop = AsyncMock()

        await outbox_daemon("token", "chat_id", shutdown_event)

        mock_instance.start.assert_called_once()
        mock_instance.stop.assert_called_once()
