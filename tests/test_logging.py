import asyncio
import io
import json
from contextlib import redirect_stdout

import pytest
import structlog

from config.logging import setup_logging, shutdown_logging

# Necesitamos probar que en contexto asíncrono cruzado las variables de contexto 
# se mantienen aisladas.

async def worker(task_id: int, delay: float):
    structlog.contextvars.bind_contextvars(task_id=task_id)
    logger = structlog.get_logger()
    
    await asyncio.sleep(delay)
    logger.info("Worker step 1")
    
    await asyncio.sleep(delay)
    logger.info("Worker step 2")

@pytest.mark.asyncio
async def test_async_context_logging():
    # Capturar la salida estándar
    f = io.StringIO()
    
    with redirect_stdout(f):
        setup_logging(json_logs=True)
        
        # Correr multiples corrutinas concurrentemente
        await asyncio.gather(
            worker(1, 0.1),
            worker(2, 0.05),
        )
        
        shutdown_logging()
    
    # Evaluar output
    output = f.getvalue()
    lines = [json.loads(line) for line in output.strip().split('\n') if line]
    
    assert len(lines) == 4, f"Expected 4 log lines, got {len(lines)}"
    
    task_1_logs = [line for line in lines if line.get("task_id") == 1]
    task_2_logs = [line for line in lines if line.get("task_id") == 2]
    
    assert len(task_1_logs) == 2
    assert len(task_2_logs) == 2
    
    for log in task_1_logs:
        assert log["task_id"] == 1
    for log in task_2_logs:
        assert log["task_id"] == 2
