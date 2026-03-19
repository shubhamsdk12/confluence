"""
Reconciliation API route — POST /api/reconcile

Accepts two interchange IDs (837 + 835) and returns a reconciliation report.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from parser.state_machine import parse_edi
from parser.delimiters import DelimiterExtractionError
from parser.identifier import IdentificationError
from database.connection import get_db
from database.repository import persist_parse_result
from reconciliation.engine import reconcile

router = APIRouter()


class ReconcileByIdRequest(BaseModel):
    claim_interchange_id: int
    remittance_interchange_id: int


@router.post("/reconcile")
async def reconcile_files(
    claim_file: UploadFile = File(...),
    remittance_file: UploadFile = File(...),
):
    """
    Upload an 837 claims file and an 835 remittance file,
    then reconcile them.
    """
    conn = await get_db()
    try:
        # Parse and persist both files
        claim_iid = await _parse_and_persist(conn, claim_file)
        remit_iid = await _parse_and_persist(conn, remittance_file)

        # Run reconciliation
        report = await reconcile(conn, claim_iid, remit_iid)
        report["claim_interchange_id"] = claim_iid
        report["remittance_interchange_id"] = remit_iid
        return report
    finally:
        await conn.close()


@router.post("/reconcile/by-id")
async def reconcile_by_ids(req: ReconcileByIdRequest):
    """Reconcile using previously-persisted interchange IDs."""
    conn = await get_db()
    try:
        report = await reconcile(conn, req.claim_interchange_id, req.remittance_interchange_id)
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
