import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from radar_social.domain.models import LicitacionCreate
from radar_social.domain.red_flags import evaluar_riesgo_licitacion

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
    hash_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    titulo: Mapped[str] = mapped_column(String(255))
    descripcion: Mapped[str] = mapped_column(String(10000))
    url_fuente: Mapped[str] = mapped_column(String(2083))
    fecha_publicacion: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    fecha_cierre: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    entidad_compradora: Mapped[str] = mapped_column(String(255))
    monto_estimado: Mapped[str] = mapped_column(
        String(50)
    )  # Persistido como TEXT para precision Decimal absoluta
    moneda: Mapped[str] = mapped_column(String(3))
    score_riesgo: Mapped[int] = mapped_column(Integer, default=0)
    banderas_rojas: Mapped[list[str]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


class OutboxEventModel(Base):
    __tablename__ = "outbox_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    event_type: Mapped[str] = mapped_column(String(50))
    payload: Mapped[dict[str, Any]] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Triggers de inmutabilidad estricta (Kardex / Ledger Inmutable)
        await conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS prevent_licitacion_update
            BEFORE UPDATE ON licitacion
            BEGIN
                SELECT RAISE(ABORT, 'Inmutabilidad violada: registro de licitacion es inmutable');
            END;
            """
        )
        await conn.exec_driver_sql(
            """
            CREATE TRIGGER IF NOT EXISTS prevent_licitacion_delete
            BEFORE DELETE ON licitacion
            BEGIN
                SELECT RAISE(ABORT, 'Inmutabilidad violada: registro de licitacion es inmutable');
            END;
            """
        )


@retry(
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=0.1, min=0.1, max=2),
    retry=retry_if_exception_type(OperationalError),
    reraise=True,
)
async def guardar_licitacion(licitacion: LicitacionCreate) -> None:
    async with AsyncSessionLocal() as session:
        async with session.begin():
            hash_id = licitacion.hash_id
            score, banderas = evaluar_riesgo_licitacion(licitacion)
            banderas_str = [b.value for b in banderas]

            db_lic = LicitacionModel(
                hash_id=hash_id,
                titulo=licitacion.titulo,
                descripcion=licitacion.descripcion,
                url_fuente=str(licitacion.url_fuente),
                fecha_publicacion=licitacion.fecha_publicacion,
                fecha_cierre=licitacion.fecha_cierre,
                entidad_compradora=licitacion.entidad_compradora,
                monto_estimado=str(licitacion.monto_estimado),
                moneda=licitacion.moneda,
                score_riesgo=score,
                banderas_rojas=banderas_str,
            )
            session.add(db_lic)

            event_payload = {
                "hash_id": hash_id,
                "titulo": licitacion.titulo,
                "url_fuente": str(licitacion.url_fuente),
                "entidad_compradora": licitacion.entidad_compradora,
                "monto_estimado": str(licitacion.monto_estimado),
                "moneda": licitacion.moneda,
                "score_riesgo": score,
                "banderas_rojas": banderas_str,
            }
            db_event = OutboxEventModel(event_type="TELEGRAM_ALERT", payload=event_payload)
            session.add(db_event)


async def obtener_licitaciones() -> list[LicitacionModel]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(LicitacionModel))
        return list(result.scalars().all())


async def obtener_eventos_outbox() -> list[OutboxEventModel]:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(OutboxEventModel))
        return list(result.scalars().all())
