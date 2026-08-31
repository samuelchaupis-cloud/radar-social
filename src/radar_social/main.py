import argparse
import asyncio
import os
import signal

import structlog

from config.log_config import setup_logging
from radar_social.daemons import crawler_daemon, outbox_daemon

logger = structlog.get_logger(__name__)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Radar Social ETL")
    subparsers = parser.add_subparsers(dest="command", required=True)

    crawler_parser = subparsers.add_parser("crawler", help="Run crawler daemon")
    crawler_parser.add_argument("--interval", type=int, default=3600, help="Interval in seconds")

    subparsers.add_parser("outbox", help="Run outbox daemon")

    all_parser = subparsers.add_parser("all", help="Run all daemons")
    all_parser.add_argument("--interval", type=int, default=3600, help="Interval in seconds")

    return parser


async def async_main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    shutdown_event = asyncio.Event()

    def handle_sigint() -> None:
        logger.info("Received interrupt signal")
        shutdown_event.set()

    loop = asyncio.get_running_loop()
    # En Windows, add_signal_handler solo soporta unos pocos seales y puede fallar.
    # Python 3.8+ maneja KeyboardInterrupt lanzando excepcion, pero podemos atraparlo as
    try:
        loop.add_signal_handler(signal.SIGINT, handle_sigint)
        loop.add_signal_handler(signal.SIGTERM, handle_sigint)
    except NotImplementedError:
        # En Windows no se puede usar add_signal_handler. Dependemos del except KeyboardInterrupt
        pass

    urls = [
        "https://www.mercadopublico.cl/Home",
    ]

    token = os.environ.get("TELEGRAM_TOKEN", "dummy")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "dummy")

    tasks = []

    if args.command in ("crawler", "all"):
        tasks.append(asyncio.create_task(crawler_daemon(urls, args.interval, shutdown_event)))

    if args.command in ("outbox", "all"):
        tasks.append(asyncio.create_task(outbox_daemon(token, chat_id, shutdown_event)))

    try:
        # Esperamos a que todas las tareas terminen
        # Solo terminaran si shutdown_event.set() es llamado
        await asyncio.gather(*tasks, return_exceptions=False)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error("Fatal error in main loop", error=str(e))
        shutdown_event.set()

    # Dar tiempo a que terminen si se lanzo la seal
    await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    setup_logging(json_logs=True)
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        logger.info("Shutting down due to KeyboardInterrupt")


if __name__ == "__main__":
    main()
