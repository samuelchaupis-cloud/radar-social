# Architecture: radar-social

## 1. Project Structure

El proyecto sigue una estructura de empaquetado estándar de Python (src-layout) para garantizar la correcta importación en los tests y el aislamiento del código fuente.

- `src/radar_social/domain/` - Modelos de dominio y validación estricta con Pydantic v2 (Capa anti-corrupción).
- `src/radar_social/etl/` - Lógica de extracción asíncrona resiliente (httpx + tenacity) y transformación defensiva (selectolax).
- `src/radar_social/infrastructure/` - Persistencia asíncrona transaccional (SQLAlchemy Async + SQLite WAL) y patrón Outbox.
- `tests/` - Suite de pruebas unitarias asíncronas con pytest y base de datos en memoria.

## 2. High-Level System Diagram

```mermaid
graph TD
    A[Crawler / Scheduler] -->|Fetch Async| B(ETL Extractor)
    B -->|Bypass / Backoff Exp| C[Target Websites]
    B -->|Raw HTML| D(ETL Transformer - selectolax)
    D -->|Validated Entities| E[Pydantic v2 Domain]
    E -->|At-Least-Once| F(SQLite Persistence)
    F -->|Insert| G[(Licitaciones Table)]
    F -->|Insert| H[(Outbox Events Table)]
    I[Outbox Dispatcher] -->|Poll| H
    I -->|Notify (Rate Limited)| J[Telegram API]
```

## 3. Tech Stack

- **Runtime**: Python 3.11+
- **Database**: SQLite (modo WAL) interactuando vía SQLAlchemy asíncrono (`aiosqlite`).
- **Data Validation**: Pydantic v2 (Modo Estricto).
- **HTTP Client**: `httpx` asíncrono.
- **Resilience / Anti-Ban**: `tenacity` para retiros exponenciales y jitter.
- **HTML Parsing**: `selectolax` para extracción defensiva y ultra-rápida evadiendo mutaciones de DOM.
- **Testing & QA**: `pytest`, `pytest-asyncio`, `ruff` (linter/formatter), `mypy` (tipado estricto), `bandit` (seguridad).

## 4. Core Components

### Extraction & Anti-Ban Resilience (Lente 1 & Lente 3)
El motor de crawling está diseñado explícitamente para sobrevivir bloqueos, WAFs y rate limits:
- Utiliza **Tenacity** para implementar una política de reintentos con *Exponential Backoff* y *Jitter* (aleatoriedad en ventanas de espera) frente a respuestas `429 Too Many Requests` y errores de conexión.
- Evade bloqueos estáticos y previene fugas de memoria al utilizar sesiones asíncronas de ciclo de vida controlado (`httpx.AsyncClient`).
- Protegido contra HTML malformado o mutante mediante `selectolax`.

### Domain Anti-Corruption Layer (Lente 2)
Todos los datos ingeridos pasan por un embudo de validación estricta (Pydantic v2), que garantiza inmutabilidad, conversión correcta (ej. fechas UTC) y descarte de payloads falsos (páginas de captura 200 OK con contenido vacío).

### Observabilidad & Logging (Lente 6)
Implementación basada en **`structlog`** con patrón *Task-Local Context* (`contextvars`). 
- Generación de NDJSON para Producción y texto coloreado tabular para Desarrollo.
- Inyección de variables asíncronas (`request_id`, `tender_hash`) atadas a la corrutina en ejecución.
- Puente no-bloqueante (`QueueHandler` + `QueueListener`) para evitar detener el event loop por cuellos de botella de I/O físico (Zero-Loss logs).

## 5. Data Stores

### SQLite (WAL Mode)
Base de datos principal integrada y sin dependencias externas, configurada de manera avanzada para alta concurrencia (`journal_mode=WAL`, `synchronous=NORMAL`, timeouts de espera de bloqueos).
- **Licitaciones**: Guarda el estado inmutable de los contratos públicos extraídos, identificados de manera única mediante deduplicación criptográfica (hash SHA-256).
- **Outbox Events**: Tabla transaccional para alertas asíncronas.

## 6. External APIs & Integrations

### Telegram Bot API
- Consumida mediante el Dispatcher (Notificador Outbox).
- Emplea rate limiting estricto (Max 30 msgs/segundo) para evitar baneos de la API.

## 7. Deployment & Infrastructure

- **VPS Single-Node (Bajo Coste):** Despliegue en un VPS simple (ej. Hetzner) apalancando la concurrencia nativa asíncrona y la resiliencia de SQLite WAL.
- **Contenerización Docker Rootless:** Dos daemons gestionados por `docker-compose` (`worker-crawler` y `worker-outbox`). Dockerfile Multi-Stage generado con `uv` para minimizar tamaño y superficie de ataque, con volumen nombrado persistente solo para SQLite `/app/data`.
- **Integración Continua (CI/CD):** Pipeline obligatorio en **GitHub Actions** aplicando *Zero-Defect Loop* (`ruff`, `mypy`, `bandit`, `pytest` >= 85%) antes del build de imágenes en GHCR.

## 8. Security & Compliance (Lente 4 & Lente 5)

- Sin llamadas de persistencia directas a API externas durante la extracción; se confía enteramente en el Patrón Outbox para garantizar que ningún dato interno filtre o se bloquee por latencia de red de un webhook.
- El proyecto impone la ejecución de **Bandit** antes de cada confirmación para auditar debilidades OWASP (ej. *hardcoded secrets*, *SQL Injections*).

## 9. Testing Strategy

- **Mutation Assertions & In-Memory DB**: Toda prueba que requiera base de datos utiliza una cadena de conexión explícita hacia SQLite `:memory:`. Se prohíbe taxativamente la cobertura sintética con `MagicMock` para la lógica de dominio.
- El umbral mínimo absoluto de *Branch Coverage* en `pytest-cov` es del 85%.

## 10. Roadmap & Future Plans

- **<!-- TODO: fill in -->** (Definir próximos objetivos arquitectónicos, paneles de observabilidad o estrategias avanzadas de proxy rotation).

## 11. Revision History

| Date | Author | Notes |
|------|--------|-------|
| 2026-08-31 | AI Agent | Initial creation documenting ETL pipeline and anti-ban capabilities |
