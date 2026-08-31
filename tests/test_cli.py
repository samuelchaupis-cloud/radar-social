from unittest.mock import AsyncMock, patch

import pytest

from radar_social.main import async_main, build_parser


def test_cli_parser():
    parser = build_parser()
    args = parser.parse_args(["crawler", "--interval", "120"])
    assert args.command == "crawler"
    assert args.interval == 120
    
    args2 = parser.parse_args(["outbox"])
    assert args2.command == "outbox"

@pytest.mark.asyncio
async def test_async_main_crawler():
    with patch("sys.argv", ["main.py", "crawler", "--interval", "1"]):
        with patch("radar_social.main.crawler_daemon", new_callable=AsyncMock) as mock_crawler:
            with patch("radar_social.main.outbox_daemon", new_callable=AsyncMock) as mock_outbox:
                await async_main()
                mock_crawler.assert_called_once()
                mock_outbox.assert_not_called()

@pytest.mark.asyncio
async def test_async_main_outbox():
    with patch("sys.argv", ["main.py", "outbox"]):
        with patch("radar_social.main.crawler_daemon", new_callable=AsyncMock) as mock_crawler:
            with patch("radar_social.main.outbox_daemon", new_callable=AsyncMock) as mock_outbox:
                await async_main()
                mock_crawler.assert_not_called()
                mock_outbox.assert_called_once()

@pytest.mark.asyncio
async def test_async_main_all():
    with patch("sys.argv", ["main.py", "all"]):
        with patch("radar_social.main.crawler_daemon", new_callable=AsyncMock) as mock_crawler:
            with patch("radar_social.main.outbox_daemon", new_callable=AsyncMock) as mock_outbox:
                await async_main()
                mock_crawler.assert_called_once()
                mock_outbox.assert_called_once()
