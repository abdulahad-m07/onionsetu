# backend/app/config/database.py
import logging
from typing import AsyncGenerator
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import declarative_base
from backend.app.config.settings import settings

logger = logging.getLogger("onionsetu.db")

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    future=True,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)

Base = declarative_base()

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_batch_model_column(conn)
        await _migrate_batch_urs_columns(conn)


async def _migrate_batch_model_column(conn):
    """Rename legacy `gemini_model` -> `assessment_model` on batch_assessments.

    Idempotent and non-destructive: data-preserving RENAME COLUMN, executed
    only when the old column exists and the new one does not. Fresh databases
    (create_all above) already have the new column. Any failure is logged —
    startup must never crash because of a migration.
    """
    try:
        def _do(sync_conn):
            insp = inspect(sync_conn)
            if "batch_assessments" not in insp.get_table_names():
                return
            cols = {c["name"] for c in insp.get_columns("batch_assessments")}
            if "gemini_model" in cols and "assessment_model" not in cols:
                sync_conn.exec_driver_sql(
                    "ALTER TABLE batch_assessments "
                    "RENAME COLUMN gemini_model TO assessment_model"
                )
                logger.info("Migrated batch_assessments.gemini_model -> assessment_model")

        await conn.run_sync(_do)
    except SQLAlchemyError as exc:
        logger.warning("Batch model-column migration skipped: %s", exc)


async def _migrate_batch_urs_columns(conn):
    """Add `urs_percent` / `assessed_onions_declared` to batch_assessments.

    Idempotent and non-destructive: plain ADD COLUMN (both nullable) executed
    only when the column is missing. Fresh databases (create_all above)
    already have them. Any failure is logged — startup must never crash
    because of a migration.
    """
    try:
        def _do(sync_conn):
            insp = inspect(sync_conn)
            if "batch_assessments" not in insp.get_table_names():
                return
            cols = {c["name"] for c in insp.get_columns("batch_assessments")}
            if "urs_percent" not in cols:
                sync_conn.exec_driver_sql(
                    "ALTER TABLE batch_assessments ADD COLUMN urs_percent FLOAT"
                )
                logger.info("Migrated batch_assessments: added urs_percent")
            if "assessed_onions_declared" not in cols:
                sync_conn.exec_driver_sql(
                    "ALTER TABLE batch_assessments "
                    "ADD COLUMN assessed_onions_declared INTEGER"
                )
                logger.info(
                    "Migrated batch_assessments: added assessed_onions_declared"
                )

        await conn.run_sync(_do)
    except SQLAlchemyError as exc:
        logger.warning("Batch URS-columns migration skipped: %s", exc)
