# Phase 2: Arquitectura de Escalamiento y Observabilidad (Zero-Defect Loop Edition)

## Goal Description
Implementar las decisiones técnicas derivadas del análisis de los agentes "Red Team" y "Data Concurrency". Se mitigarán cuellos de botella de SQLite, fugas de memoria, bloqueos WAF, e ineficiencias de I/O asíncrono.

## Tareas

### Task 1: Refactorización Pydantic y Normalización Criptográfica
- **Lente 4 & 5 (Memoria e Integridad):**
- Modificar `LicitacionCreate`: Añadir `max_length` estricto a `titulo`, `descripcion` y `url_fuente` para prevenir ataques de consumo de RAM (DoS por JSON infinito).
- Añadir normalización estricta de strings (trim, lowercase) previa al hash SHA-256 para evitar duplicados en la base de datos por caracteres invisibles.

### Task 2: Refactorización Anti-Scraping (curl_cffi) & Backpressure
- **Lente 1 & 4 (Evasión WAF y RAM < 45MB):**
- Reemplazar `httpx` por `curl_cffi` para spoofing (JA3/JA4).
- Ajustar el decorador `tenacity` para **inyectar un proxy Datacenter fresco en CADA reintento**, no reusando proxies quemados.
- Implementar `asyncio.Semaphore(10)` para limitar concurrencia de sockets.
- Aislar `selectolax` en `asyncio.to_thread()` evitando bloqueos de CPU en el Event Loop.

### Task 3: Defensas de Concurrencia Extrema en SQLite (aiosqlite)
- **Lente 2 (Transaccional):**
- Configurar el engine SQLAlchemy con eventos explícitos: `PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL; PRAGMA busy_timeout=5000;`.
- Forzar `BEGIN IMMEDIATE` en la sesión de escritura para evitar deadlocks de escalamiento.
- Extraer CUALQUIER llamada de red fuera del contexto `session.begin()`.
- Agregar decoradores `tenacity` atrapando `OperationalError: database is locked`.

### Task 4: Observabilidad y Logs Asíncronos Seguros
- **Lente 6 (Observabilidad):**
- Integrar `structlog` usando el patrón *Task-Local Context* (`contextvars` para `request_id`).
- Configurar un puente `QueueHandler` + `QueueListener` para evitar bloquear I/O.
- Manejar `SIGTERM` con *Graceful Shutdown* parando el listener de logs de forma ordenada.

### Task 5: Patrón Outbox Estrangulado
- **Lente 3 (Resiliencia):**
- Refactorizar el "Outbox Dispatcher" para usar Polling con *Exponential Backoff* (evitando thrashing del disco con SELECTs infinitos vacíos).
- Implementar **Batching estricto (Max 20 msgs/min)** para evitar baneos de Telegram API.
- Actualizar el test `test_database.py` para utilizar un archivo temporal `tmp/test.db` y descartar SQLite `:memory:` para pruebas de concurrencia.

### Task 6: Contenerización Rootless Multi-Stage
- Crear `Dockerfile` basado en `uv` (multi-stage).
- Ejecutar el comando `mkdir -p /app/data && chown -R appuser:appuser /app/data` antes de hacer el cambio `USER appuser`, previniendo errores de volumen montado en root.
- Definir `docker-compose.yml` ejecutando `worker-crawler` y `worker-outbox`.
