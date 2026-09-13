# backend/tests/test_migrations.py
"""Database migration safety tests.

- Legacy databases carrying batch_assessments.gemini_model must be migrated
  to assessment_model with all rows preserved (non-destructive rename).
- Legacy databases predating the URS columns must gain nullable
  urs_percent / assessed_onions_declared without touching existing rows.
- Migrations must be idempotent and must never crash startup.
"""
import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession, create_async_engine
from sqlalchemy.future import select

from backend.app.config.database import (
    _migrate_batch_model_column,
    _migrate_batch_urs_columns,
)
from backend.app.models.batch import BatchAssessment


@pytest.mark.asyncio
async def test_legacy_gemini_column_renamed_with_data_preserved(tmp_path):
    db_path = tmp_path / "legacy.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    try:
        async with engine.begin() as conn:
            await conn.exec_driver_sql(
                "CREATE TABLE batch_assessments ("
                "id TEXT PRIMARY KEY, scan_id TEXT, status TEXT, "
                "final_grade TEXT, assessment_confidence FLOAT, "
                "sample_size INTEGER, sample_size_estimated BOOLEAN, "
                "images_analyzed INTEGER, review_required BOOLEAN, "
                "review_reasons_json TEXT, policy_version TEXT, "
                "roboflow_model TEXT, gemini_model TEXT, "
                "observations_json TEXT, issues_json TEXT, "
                "evidence_json TEXT, calculated_at DATETIME)"
            )
            await conn.exec_driver_sql(
                "INSERT INTO batch_assessments (id, final_grade, gemini_model) "
                "VALUES ('b1', 'B', 'gemini-3.1-pro-preview')"
            )
            # Run twice: migrations must be idempotent.
            await _migrate_batch_model_column(conn)
            await _migrate_batch_model_column(conn)
            await _migrate_batch_urs_columns(conn)
            await _migrate_batch_urs_columns(conn)

        Session = async_sessionmaker(
            bind=engine, class_=AsyncSession, expire_on_commit=False
        )
        async with Session() as session:
            row = (
                await session.execute(
                    select(BatchAssessment).where(BatchAssessment.id == "b1")
                )
            ).scalar_one()
            assert row.assessment_model == "gemini-3.1-pro-preview"
            assert row.final_grade == "B"
            # URS columns backfilled as nullable: old rows carry no URS
            # evidence rather than an invented zero.
            assert row.urs_percent is None
            assert row.assessed_onions_declared is None
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_migration_noop_without_table_never_crashes(tmp_path):
    db_path = tmp_path / "empty.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    try:
        async with engine.begin() as conn:
            # No tables at all: must silently do nothing, never raise.
            await _migrate_batch_model_column(conn)
    finally:
        await engine.dispose()
