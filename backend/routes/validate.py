"""
Validate API route — POST /api/validate

Accepts an EDI file upload, parses it, persists to SQLite,
runs SNIP 1-3 validation, and returns the results.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File

from parser.state_machine import parse_edi
from parser.delimiters import DelimiterExtractionError
from parser.identifier import IdentificationError
from database.connection import get_db
from database.repository import persist_parse_result
from validator.engine import validate

router = APIRouter()

_MAX_FILE_SIZE = 10 * 1024 * 1024
_ALLOWED_EXTENSIONS = {".edi", ".txt", ".dat", ".x12"}


@router.post("/validate")
async def validate_file(file: UploadFile = File(...)):
    """
    Upload, parse, persist, and validate an EDI file.

    Returns: {
        interchange_id,
        parse_result,
        validation_errors[],
        summary: { snip1_errors, snip2_errors, snip3_errors, total_errors, total_warnings }
    }
    """
    # Validate extension
    filename = file.filename or ""
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()
    if ext and ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail={
                "message": f"Unsupported file type: '{ext}'. Accepted: {', '.join(_ALLOWED_EXTENSIONS)}",
                "code": "INVALID_FILE_TYPE",
            },
        )

    # Read content
    content_bytes = await file.read()
    if len(content_bytes) > _MAX_FILE_SIZE:
        raise HTTPException(
            status_code=413,
            detail={
                "message": f"File exceeds maximum size of {_MAX_FILE_SIZE // (1024*1024)} MB",
                "code": "FILE_TOO_LARGE",
            },
        )

    # Decode
    try:
        raw = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raw = content_bytes.decode("latin-1")

    # Parse
    try:
        result = parse_edi(raw)
    except DelimiterExtractionError as e:
        raise HTTPException(
            status_code=422,
            detail={"message": str(e), "code": "DELIMITER_ERROR"},
        )
    except IdentificationError as e:
        raise HTTPException(
            status_code=422,
            detail={"message": str(e), "code": "IDENTIFICATION_ERROR"},
        )

    # Persist + Validate
    conn = await get_db()
    try:
        interchange_id = await persist_parse_result(conn, filename, result)
        errors = await validate(conn, interchange_id)
    finally:
        await conn.close()

    # Build summary
    snip1 = sum(1 for e in errors if e.snip_level == 1)
    snip2 = sum(1 for e in errors if e.snip_level == 2)
    snip3 = sum(1 for e in errors if e.snip_level == 3)
    total_errors = sum(1 for e in errors if e.severity.value == "error")
    total_warnings = sum(1 for e in errors if e.severity.value == "warning")

    return {
        "interchange_id": interchange_id,
        "parse_result": result.model_dump(),
        "validation_errors": [e.model_dump() for e in errors],
        "summary": {
            "snip1_errors": snip1,
            "snip2_errors": snip2,
            "snip3_errors": snip3,
            "total_errors": total_errors,
            "total_warnings": total_warnings,
        },
    }
