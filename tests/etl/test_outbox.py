import os
import tempfile
from unittest.mock import AsyncMock, patch

import pytest

# Create a temporary real DB to avoid in-memory issues, like test_database.py
fd, test_db_path = tempfile.mkstemp(suffix=".db")
os.close(fd)
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{test_db_path}"

from sqlalchemy import text  # noqa: E402

from radar_social.etl.outbox import OutboxDispatcher  # noqa: E402
from radar_social.infrastructure.database import (  # noqa: E402
    AsyncSessionLocal,
    OutboxEventModel,
    init_db,
)


@pytest.fixture(autouse=True)
async def setup_db():
    await init_db()
    # Clean up table before each test
    async with AsyncSessionLocal() as session:
        async with session.begin():
            await session.execute(OutboxEventModel.__table__.delete())
    yield


@pytest.mark.asyncio
async def test_outbox_dispatcher_batching_and_throttle():
    # Insert 25 pending messages (exceeding MAX_BATCH_SIZE of 20)
    async with AsyncSessionLocal() as session:
        async with session.begin():
            for i in range(25):
                evt = OutboxEventModel(
                    event_type="TELEGRAM_ALERT",
                    payload={"titulo": f"Test {i}", "url_fuente": f"http://test.com/{i}"},
                    status="PENDING",
                )
                session.add(evt)

    dispatcher = OutboxDispatcher("fake-token", "fake-chat-id")

    # Mock network I/O
    mock_post = AsyncMock()

    # We will step through the loop manually to control execution and avoid infinite loop in tests
    with patch.object(dispatcher, "_http_post", mock_post):
        # Process first batch
        processed = await dispatcher._process_batch()
        assert processed == 20
        assert mock_post.call_count == 20

        # Process second batch (remaining 5)
        processed_2 = await dispatcher._process_batch()
        assert processed_2 == 5
        assert mock_post.call_count == 25

        # Ensure all are marked SENT
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT count(*) FROM outbox_events WHERE status = 'SENT'")
            )
            count = result.scalar()
            assert count == 25


@pytest.mark.asyncio
async def test_outbox_dispatcher_polling_loop_with_sleep():
    dispatcher = OutboxDispatcher("fake-token", "fake-chat-id")

    # We want to test that when no messages exist, it sleeps for SLEEP_NO_MESSAGES
    # and when messages exist, it sleeps for RATE_LIMIT_WAIT
    mock_sleep = AsyncMock()

    async def stop_after_one_loop(*args, **kwargs):
        dispatcher._running = False

    mock_sleep.side_effect = stop_after_one_loop

    with patch("radar_social.etl.outbox.asyncio.sleep", mock_sleep):
        # 1. Test empty db (no messages)
        dispatcher._running = True
        await dispatcher._loop()
        mock_sleep.assert_called_once_with(2.0)

        mock_sleep.reset_mock()

        # 2. Add a message and test rate limit sleep
        async with AsyncSessionLocal() as session:
            async with session.begin():
                evt = OutboxEventModel(
                    event_type="TELEGRAM_ALERT",
                    payload={"titulo": "Test", "url_fuente": "http://test.com"},
                    status="PENDING",
                )
                session.add(evt)

        mock_post = AsyncMock()
        mock_sleep.side_effect = stop_after_one_loop

        with patch.object(dispatcher, "_http_post", mock_post):
            dispatcher._running = True
            await dispatcher._loop()

            mock_post.assert_called_once()
            mock_sleep.assert_called_once_with(60.0)


@pytest.mark.asyncio
async def test_outbox_dispatcher_retry_on_failure():
    # Insert 1 message
    async with AsyncSessionLocal() as session:
        async with session.begin():
            evt = OutboxEventModel(
                event_type="TELEGRAM_ALERT",
                payload={"titulo": "Fail Test", "url_fuente": "http://fail.com"},
                status="PENDING",
            )
            session.add(evt)

    dispatcher = OutboxDispatcher("fake-token", "fake-chat-id")

    # Mock network I/O to fail constantly
    mock_post = AsyncMock(side_effect=Exception("Network error"))

    with patch.object(dispatcher, "_http_post", mock_post):
        processed = await dispatcher._process_batch()
        assert processed == 0  # no messages successfully processed

        # tenacity should have retried 3 times (based on stop_after_attempt(3))
        assert mock_post.call_count == 3

        # Check DB status is FAILED
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                text("SELECT count(*) FROM outbox_events WHERE status = 'FAILED'")
            )
            count = result.scalar()
            assert count == 1
