import hashlib
import json
import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from radar_social.domain.models import LicitacionCreate

# SQLite en archivo por defecto para soportar concurrencia REAL.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///radar_social.db")

engine = create_async_engine(DATABASE_URL, echo=False, connect_args={"check_same_thread": False})


@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection: Any, connection_record: Any) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


@event.listens_for(engine.sync_engine, "begin")
def do_begin(conn: Any) -> None:
    conn.exec_driver_sql("BEGIN IMMEDIATE")


AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class LicitacionModel(Base):
    __tablename__ = "licitacion"
    hash_id: Mapped[str] = mapped_column(String, primary_key=True)
    titulo: Mapped[str] = mapped_column(String)
    descripcion: Mapped[str] = mapped_column(String)
    url_fuente: Mapped[str] = mapped_column(String)
    fecha_publicacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String)
    payload: Mapped[str] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String, default="PENDING")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def calcular_hash(lic: LicitacionCreate) -> str:
    cadena = f"{lic.titulo}{lic.descripcion}{lic.fecha_publicacion.isoformat()}"
    return hashlib.sha256(cadena.encode("utf-8")).hexdigest()


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=2),
    retry=retry_if_exception_type(OperationalError),
    reraise=True,
)
async def guardar_licitacion(licitacion: LicitacionCreate) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            hash_id = calcular_hash(licitacion)

            db_lic = LicitacionModel(
                hash_id=hash_id,
                titulo=licitacion.titulo,
                descripcion=licitacion.descripcion,
                url_fuente=str(licitacion.url_fuente),
                fecha_publicacion=licitacion.fecha_publicacion,
            )
            session.add(db_lic)

            payload = licitacion.model_dump_json()
            db_event = OutboxEventModel(event_type="TELEGRAM_ALERT", payload=json.loads(payload))
            session.add(db_event)


async def obtener_licitaciones() -> list[LicitacionModel]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(LicitacionModel))
        return list(result.scalars().all())


async def obtener_eventos_outbox() -> list[OutboxEventModel]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OutboxEventModel))
        return list(result.scalars().all())
