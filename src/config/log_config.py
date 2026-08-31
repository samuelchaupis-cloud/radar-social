import logging
import logging.config
import queue
import sys
from logging.handlers import QueueHandler, QueueListener

import structlog
from structlog.types import Processor

# Global reference to the listener so it can be stopped on shutdown
_log_listener: QueueListener | None = None


def setup_logging(json_logs: bool = True) -> None:
    global _log_listener

    # Limpiar configuración previa si se llama múltiples veces
    if _log_listener is not None:
        _log_listener.stop()
        logging.getLogger().handlers.clear()

    # Shared structlog processors
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Formatter
    if json_logs:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.processors.JSONRenderer(),
            foreign_pre_chain=shared_processors,
        )
    else:
        formatter = structlog.stdlib.ProcessorFormatter(
            processor=structlog.dev.ConsoleRenderer(),
            foreign_pre_chain=shared_processors,
        )

    # El handler destino (stdout)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    class StructlogQueueHandler(QueueHandler):
        def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
            # Structlog necesita el dict original, retornamos el record intacto.
            return record

    # Usamos una cola acotada para evitar OOM (Memory Leak Lente 4)
    log_queue: queue.Queue[logging.LogRecord] = queue.Queue(maxsize=10000)
    queue_handler = StructlogQueueHandler(log_queue)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = []
    root_logger.addHandler(queue_handler)

    # Iniciamos el listener
    _log_listener = QueueListener(log_queue, stream_handler, respect_handler_level=True)
    _log_listener.start()


def shutdown_logging() -> None:
    """Graceful shutdown para el logger asíncrono.
    Asegura que los logs en la cola se flusheen al destino antes de salir.
    """
    global _log_listener
    if _log_listener is not None:
        _log_listener.stop()
        _log_listener = None
