"""
Delta API route — POST /api/delta

Accepts two 834 enrollment files and returns a member delta report.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from parser.state_machine import parse_edi
from parser.delimiters import DelimiterExtractionError
from parser.identifier import IdentificationError
from database.connection import get_db
from database.repository import persist_parse_result
from delta.engine import compute_delta

router = APIRouter()


class DeltaByIdRequest(BaseModel):
    old_interchange_id: int
    new_interchange_id: int


@router.post("/delta")
async def delta_files(
    old_file: UploadFile = File(...),
    new_file: UploadFile = File(...),
):
    """
    Upload two 834 enrollment files (old and new) and compute the delta.
    """
    conn = await get_db()
    try:
        old_iid = await _parse_and_persist(conn, old_file)
        new_iid = await _parse_and_persist(conn, new_file)

        report = await compute_delta(conn, old_iid, new_iid)
        report["old_interchange_id"] = old_iid
        report["new_interchange_id"] = new_iid
        return report
    finally:
        await conn.close()


@router.post("/delta/by-id")
async def delta_by_ids(req: DeltaByIdRequest):
    """Compute delta using previously-persisted interchange IDs."""
    conn = await get_db()
    try:
        report = await compute_delta(conn, req.old_interchange_id, req.new_interchange_id)
        return report
    finally:
        await conn.close()


async def _parse_and_persist(conn, file: UploadFile) -> int:
    """Helper: read, parse, persist, return interchange_id."""
    content = await file.read()
    try:
        raw = content.decode("utf-8")
    except UnicodeDecodeError:
        raw = content.decode("latin-1")

    try:
        result = parse_edi(raw)
    except (DelimiterExtractionError, IdentificationError) as e:
        raise HTTPException(status_code=422, detail=str(e))

    return await persist_parse_result(conn, file.filename or "unknown", result)
