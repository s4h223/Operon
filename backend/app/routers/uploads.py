from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.core.config import MAX_UPLOAD_BYTES
from app.database.connection import db_lock
from app.database.schema import ALL_ENTITY_TYPES
from app.ingestion.parser import CsvParseError, dataframe_preview, read_csv_flexible
from app.ingestion.upload_service import get_upload_meta, get_upload_path, save_upload
from app.models.schemas import MappingRequest, ProcessResult, UploadResponse
from app.normalization.transform import transform_and_load

router = APIRouter(prefix="/api/uploads", tags=["uploads"])


@router.post("", response_model=UploadResponse)
async def create_upload(
    file: UploadFile = File(...),
    entity_type: str = Form(...),
) -> UploadResponse:
    if entity_type not in ALL_ENTITY_TYPES:
        raise HTTPException(400, f"entity_type must be one of {ALL_ENTITY_TYPES}")
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(400, "Only .csv files are supported.")

    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File exceeds maximum upload size.")
    if not content:
        raise HTTPException(400, "Uploaded file is empty.")

    try:
        return save_upload(file.filename, entity_type, content)
    except CsvParseError as e:
        raise HTTPException(400, str(e)) from e


@router.get("")
def list_uploads() -> list[dict]:
    with db_lock() as conn:
        rows = conn.execute(
            """
            SELECT upload_id, filename, entity_type, status, row_count, column_count, uploaded_at
            FROM uploads ORDER BY uploaded_at DESC
            """
        ).fetchall()
        cols = [d[0] for d in conn.description]
    return [dict(zip(cols, r)) for r in rows]


@router.get("/{upload_id}")
def get_upload(upload_id: str) -> dict:
    try:
        return get_upload_meta(upload_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e


@router.get("/{upload_id}/preview")
def preview_upload(upload_id: str, n: int = 20) -> dict:
    try:
        path = get_upload_path(upload_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    try:
        df = read_csv_flexible(path, nrows=n)
    except CsvParseError as e:
        raise HTTPException(400, str(e)) from e
    return {"columns": [str(c) for c in df.columns], "rows": dataframe_preview(df, n=n)}


@router.post("/{upload_id}/process", response_model=ProcessResult)
def process_upload(upload_id: str, body: MappingRequest) -> ProcessResult:
    if body.upload_id != upload_id:
        raise HTTPException(400, "upload_id in path and body must match.")
    try:
        get_upload_meta(upload_id)
    except KeyError as e:
        raise HTTPException(404, str(e)) from e
    if not body.mapping:
        raise HTTPException(400, "mapping must not be empty.")
    return transform_and_load(upload_id, body.mapping)
