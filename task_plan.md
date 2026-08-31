# Diseño de Tubería ETL Asíncrona Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) o superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar una tubería ETL asíncrona y resiliente para extraer, validar y almacenar datos de licitaciones utilizando Pydantic v2, selectolax, httpx y SQLite en modo WAL, garantizando el patrón Outbox para notificaciones.

**Architecture:** El sistema utilizará asyncio para concurrencia. La extracción se hará con httpx y tenacity para retiros exponenciales. El parsing con selectolax. La validación (anti-corruption layer) empleará Pydantic v2 de forma estricta. La persistencia se basará en SQLAlchemy asíncrono con SQLite en modo WAL para la tabla principal y la tabla outbox (patrón Store-and-Forward).

**Tech Stack:** Python 3.11+, httpx, selectolax, pydantic v2, sqlalchemy (async), pytest-asyncio.

**Spec:** IMPLEMENTATION_PLAN.md

## Global Constraints

- Todos los mensajes de commit, documentación y código deben estar 100% en ESPAÑOL técnico formal.
- Uso de SQLite en modo `:memory:` es obligatorio para tests de base de datos.
- Prohibido el uso de `# type: ignore`, `# noqa`, `# nosec` o comodines como `Any`.
- `uv run ruff check .`, `uv run ruff format --check .`, `uv run mypy src/`, y `uv run pytest tests/ -v --cov=src --cov-fail-under=85` deben pasar sin errores.
- Mutaciones de estado real en los tests, cobertura > 85% sin usar MagicMock para persistencia local.

---

### Task 1: Modelos de Dominio y Validación (Pydantic v2)

**Files:**
- Create: `src/radar_social/domain/models.py`
- Create: `tests/domain/test_models.py`

**Interfaces:**
- Produces: `LicitacionBase`, `LicitacionCreate`, `Licitacion` (Pydantic models)

- [ ] **Step 1: Escribir test fallido para la validación de Licitacion**

```python
import pytest
from pydantic import ValidationError
from radar_social.domain.models import LicitacionCreate
from datetime import datetime, timezone

def test_licitacion_create_validacion_estricta():
    # Falla intencionalmente por tipos incorrectos
    with pytest.raises(ValidationError):
        LicitacionCreate(
            titulo=123,
            descripcion="Descripción válida",
            url_fuente="http://ejemplo.com",
            fecha_publicacion="no-una-fecha"
        )
    
    # Éxito con datos correctos
    dt = datetime.now(timezone.utc)
    lic = LicitacionCreate(
        titulo="Licitacion 1",
        descripcion="Desc",
        url_fuente="http://ejemplo.com",
        fecha_publicacion=dt
    )
    assert lic.titulo == "Licitacion 1"
```

- [ ] **Step 2: Ejecutar test para verificar que falla**

Run: `uv run pytest tests/domain/test_models.py -v`
Expected: FAIL con "ModuleNotFoundError"

- [ ] **Step 3: Implementar modelos Pydantic v2**

```python
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from datetime import datetime

class LicitacionBase(BaseModel):
    model_config = ConfigDict(strict=True)
    titulo: str = Field(min_length=5)
    descripcion: str
    url_fuente: HttpUrl
    fecha_publicacion: datetime

class LicitacionCreate(LicitacionBase):
    pass

class Licitacion(LicitacionBase):
    hash_id: str
    created_at: datetime
```

- [ ] **Step 4: Ejecutar test para verificar que pasa**

Run: `uv run pytest tests/domain/test_models.py -v`
Expected: PASS

- [ ] **Step 5: Hacer commit**

```bash
git add tests/domain/test_models.py src/radar_social/domain/models.py
git commit -m "feat: implementar modelos de dominio estrictos con pydantic v2"
```

### Task 2: Cliente HTTP Resiliente (httpx + tenacity)

**Files:**
- Create: `src/radar_social/etl/extract.py`
- Create: `tests/etl/test_extract.py`

**Interfaces:**
- Consumes: nada
- Produces: `async def extraer_html_resiliente(url: str) -> str`

- [ ] **Step 1: Escribir test fallido para extracción con retiros**

```python
import pytest
import httpx
from radar_social.etl.extract import extraer_html_resiliente

@pytest.mark.asyncio
async def test_extraer_html_resiliente_exito(httpx_mock):
    httpx_mock.add_response(url="http://ejemplo.com", text="<html>OK</html>")
    resultado = await extraer_html_resiliente("http://ejemplo.com")
    assert resultado == "<html>OK</html>"
```

- [ ] **Step 2: Ejecutar test para verificar que falla**

Run: `uv run pytest tests/etl/test_extract.py -v`
Expected: FAIL con "ImportError"

- [ ] **Step 3: Implementar extractor con tenacity**

```python
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

@retry(
    wait=wait_exponential(multiplier=1, min=4, max=10),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
)
async def extraer_html_resiliente(url: str) -> str:
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text
```

- [ ] **Step 4: Ejecutar test para verificar que pasa**

Run: `uv run pytest tests/etl/test_extract.py -v`
Expected: PASS

- [ ] **Step 5: Hacer commit**

```bash
git add tests/etl/test_extract.py src/radar_social/etl/extract.py
git commit -m "feat: implementar cliente http asíncrono con retiros exponenciales"
```

### Task 3: Parser Defensivo (selectolax)

**Files:**
- Create: `src/radar_social/etl/transform.py`
- Create: `tests/etl/test_transform.py`

**Interfaces:**
- Consumes: `LicitacionCreate`
- Produces: `def parsear_licitacion(html: str) -> LicitacionCreate`

- [ ] **Step 1: Escribir test fallido para parsing**

```python
import pytest
from datetime import datetime, timezone
from radar_social.etl.transform import parsear_licitacion
from radar_social.domain.models import LicitacionCreate
from pydantic import ValidationError

def test_parsear_licitacion_valida():
    html = '''
    <div class="licitacion">
        <h1 class="titulo">Construcción de Escuela</h1>
        <p class="desc">Detalles del proyecto de obra</p>
        <span class="fecha">2026-08-31T10:00:00Z</span>
        <a class="enlace" href="http://ejemplo.com/lic/1">Enlace</a>
    </div>
    '''
    resultado = parsear_licitacion(html)
    assert resultado.titulo == "Construcción de Escuela"
    assert resultado.descripcion == "Detalles del proyecto de obra"

def test_parsear_licitacion_incompleta():
    html = '<div class="licitacion"><h1 class="titulo">Incompleto</h1></div>'
    with pytest.raises(ValueError):
        parsear_licitacion(html)
```

- [ ] **Step 2: Ejecutar test para verificar que falla**

Run: `uv run pytest tests/etl/test_transform.py -v`
Expected: FAIL con "ImportError"

- [ ] **Step 3: Implementar parser con selectolax**

```python
from selectolax.parser import HTMLParser
from radar_social.domain.models import LicitacionCreate
from datetime import datetime

def parsear_licitacion(html: str) -> LicitacionCreate:
    tree = HTMLParser(html)
    titulo_node = tree.css_first(".titulo")
    desc_node = tree.css_first(".desc")
    fecha_node = tree.css_first(".fecha")
    enlace_node = tree.css_first(".enlace")

    if not all([titulo_node, desc_node, fecha_node, enlace_node]):
        raise ValueError("HTML malformado o elementos faltantes")

    titulo = titulo_node.text(strip=True) if titulo_node else ""
    desc = desc_node.text(strip=True) if desc_node else ""
    fecha_str = fecha_node.text(strip=True) if fecha_node else ""
    url = enlace_node.attributes.get("href", "") if enlace_node else ""

    if not url:
        raise ValueError("URL no encontrada en el enlace")

    fecha = datetime.fromisoformat(fecha_str.replace("Z", "+00:00"))

    return LicitacionCreate(
        titulo=titulo,
        descripcion=desc,
        url_fuente=url,
        fecha_publicacion=fecha
    )
```

- [ ] **Step 4: Ejecutar test para verificar que pasa**

Run: `uv run pytest tests/etl/test_transform.py -v`
Expected: PASS

- [ ] **Step 5: Hacer commit**

```bash
git add tests/etl/test_transform.py src/radar_social/etl/transform.py
git commit -m "feat: implementar parser defensivo de HTML usando selectolax"
```

### Task 4: Base de Datos y Patrón Outbox (SQLAlchemy Async)

**Files:**
- Create: `src/radar_social/infrastructure/database.py`
- Create: `tests/infrastructure/test_database.py`

**Interfaces:**
- Consumes: `LicitacionCreate`
- Produces: `async def guardar_licitacion(licitacion: LicitacionCreate)`

- [ ] **Step 1: Escribir test fallido para persistencia**

```python
import pytest
import asyncio
from radar_social.infrastructure.database import guardar_licitacion, obtener_licitaciones, obtener_eventos_outbox, init_db
from radar_social.domain.models import LicitacionCreate
from datetime import datetime, timezone

@pytest.mark.asyncio
async def test_guardar_licitacion_transaccional():
    await init_db()
    
    lic = LicitacionCreate(
        titulo="Licitacion Prueba",
        descripcion="Desc",
        url_fuente="http://ejemplo.com",
        fecha_publicacion=datetime.now(timezone.utc)
    )
    
    await guardar_licitacion(lic)
    
    licitaciones = await obtener_licitaciones()
    assert len(licitaciones) == 1
    assert licitaciones[0].titulo == "Licitacion Prueba"
    
    eventos = await obtener_eventos_outbox()
    assert len(eventos) == 1
    assert eventos[0].event_type == "TELEGRAM_ALERT"
```

- [ ] **Step 2: Ejecutar test para verificar que falla**

Run: `uv run pytest tests/infrastructure/test_database.py -v`
Expected: FAIL con ImportError

- [ ] **Step 3: Implementar DB en SQLite :memory: con SQLAlchemy**

```python
import json
import hashlib
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Integer, DateTime, JSON
from radar_social.domain.models import LicitacionCreate

# SQLite en memoria por defecto para tests, journal_mode WAL configurado vía SQLAlchemy connect_args si se requiere.
DATABASE_URL = "sqlite+aiosqlite:///:memory:"

engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    connect_args={"check_same_thread": False}
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False
)

class Base(DeclarativeBase):
    pass

class LicitacionModel(Base):
    __tablename__ = "licitacion"
    hash_id: Mapped[str] = mapped_column(String, primary_key=True)
    titulo: Mapped[str] = mapped_column(String)
    descripcion: Mapped[str] = mapped_column(String)
    url_fuente: Mapped[str] = mapped_column(String)
    fecha_publicacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

class OutboxEventModel(Base):
    __tablename__ = "outbox_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String)
    payload: Mapped[str] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

def calcular_hash(lic: LicitacionCreate) -> str:
    cadena = f"{lic.titulo}{lic.descripcion}{lic.fecha_publicacion.isoformat()}"
    return hashlib.sha256(cadena.encode('utf-8')).hexdigest()

async def guardar_licitacion(licitacion: LicitacionCreate) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            hash_id = calcular_hash(licitacion)
            
            db_lic = LicitacionModel(
                hash_id=hash_id,
                titulo=licitacion.titulo,
                descripcion=licitacion.descripcion,
                url_fuente=str(licitacion.url_fuente),
                fecha_publicacion=licitacion.fecha_publicacion
            )
            session.add(db_lic)
            
            payload = licitacion.model_dump_json()
            db_event = OutboxEventModel(
                event_type="TELEGRAM_ALERT",
                payload=json.loads(payload)
            )
            session.add(db_event)

async def obtener_licitaciones() -> list[LicitacionModel]:
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(LicitacionModel))
        return list(result.scalars().all())

async def obtener_eventos_outbox() -> list[OutboxEventModel]:
    from sqlalchemy import select
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OutboxEventModel))
        return list(result.scalars().all())
```

- [ ] **Step 4: Ejecutar test para verificar que pasa**

Run: `uv run pytest tests/infrastructure/test_database.py -v`
Expected: PASS

- [ ] **Step 5: Hacer commit**

```bash
git add tests/infrastructure/test_database.py src/radar_social/infrastructure/database.py
git commit -m "feat: implementar persistencia asíncrona con sqlite y patrón outbox"
```
