"""Upload orchestration: persist the raw file, register it, compute preview
and suggested mapping. Business logic lives here, not in the route handler."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.config import UPLOADS_DIR
from app.database.connection import db_lock
from app.database.schema import REQUIRED_FIELDS
from app.ingestion.parser import CsvParseError, dataframe_preview, read_csv_flexible
from app.ingestion.validation import validate_dataframe
from app.models.schemas import (
    MappingSuggestion,
    UploadResponse,
    ValidationSummary,
)
from app.normalization.mapper import missing_required_fields, suggest_mapping


def save_upload(filename: str, entity_type: str, content: bytes) -> UploadResponse:
    upload_id = str(uuid.uuid4())
    dest = UPLOADS_DIR / f"{upload_id}.csv"
    dest.write_bytes(content)

    try:
        df = read_csv_flexible(dest)
    except CsvParseError as e:
        dest.unlink(missing_ok=True)
        raise

    warnings = validate_dataframe(df)
    columns = [str(c) for c in df.columns]
    suggestion_map = suggest_mapping(entity_type, columns)
    suggested_mapping = {
        col: MappingSuggestion(
            standard_field=s.standard_field, confidence=s.confidence, alternatives=s.alternatives
        )
        for col, s in suggestion_map.items()
    }

    auto_mapping = {
        col: s.standard_field for col, s in suggestion_map.items() if s.standard_field
    }
    missing_required = missing_required_fields(
        entity_type, auto_mapping, REQUIRED_FIELDS[entity_type]
    )

    validation = ValidationSummary(
        is_valid=len(missing_required) == 0,
        missing_required_after_mapping=missing_required,
        warnings=warnings,
        error_rows=0,
    )

    row_count = int(len(df))
    with db_lock() as conn:
        conn.execute(
            """
            INSERT INTO uploads
                (upload_id, filename, entity_type, status, row_count, column_count,
                 raw_path, uploaded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                upload_id,
                filename,
                entity_type,
                "uploaded",
                row_count,
                len(columns),
                str(dest),
                datetime.now(timezone.utc),
            ],
        )
        for col, sugg in suggested_mapping.items():
            conn.execute(
                """
                INSERT INTO column_mappings (upload_id, raw_column, standard_field, confidence)
                VALUES (?, ?, ?, ?)
                """,
                [upload_id, col, sugg.standard_field, sugg.confidence],
            )

    return UploadResponse(
        upload_id=upload_id,
        filename=filename,
        entity_type=entity_type,
        row_count=row_count,
        column_count=len(columns),
        columns=columns,
        preview_rows=dataframe_preview(df, n=20),
        suggested_mapping=suggested_mapping,
        validation=validation,
    )


def get_upload_path(upload_id: str) -> Path:
    with db_lock() as conn:
        row = conn.execute(
            "SELECT raw_path FROM uploads WHERE upload_id = ?", [upload_id]
        ).fetchone()
    if row is None:
        raise KeyError(f"Unknown upload_id: {upload_id}")
    return Path(row[0])


def get_upload_meta(upload_id: str) -> dict:
    with db_lock() as conn:
        row = conn.execute(
            """
            SELECT upload_id, filename, entity_type, status, row_count, column_count,
                   raw_path, uploaded_at
            FROM uploads WHERE upload_id = ?
            """,
            [upload_id],
        ).fetchone()
    if row is None:
        raise KeyError(f"Unknown upload_id: {upload_id}")
    cols = [
        "upload_id", "filename", "entity_type", "status", "row_count", "column_count",
        "raw_path", "uploaded_at",
    ]
    return dict(zip(cols, row))
