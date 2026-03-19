"""
Parse API route — POST /api/parse

Accepts an EDI file upload, runs the state-machine parser,
persists the result to SQLite, and returns the interchange_id
alongside the hierarchical ParseResult JSON.
"""
from fastapi import APIRouter, HTTPException, UploadFile, File

from parser.state_machine import parse_edi
from parser.delimiters import DelimiterExtractionError
from parser.identifier import IdentificationError
from database.connection import get_db
from database.repository import persist_parse_result

router = APIRouter()

# Maximum upload size: 10 MB
_MAX_FILE_SIZE = 10 * 1024 * 1024

_ALLOWED_EXTENSIONS = {".edi", ".txt", ".dat", ".x12"}


@router.post("/parse")
async def parse_file(file: UploadFile = File(...)):
    """
    Upload, parse, and persist an EDI file.

    Accepts: .edi, .txt, .dat, .x12 files
    Returns: { interchange_id, parse_result }
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

    # Decode — try UTF-8 first, fall back to latin-1 (common in legacy EDI)
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

    # Persist to SQLite
    conn = await get_db()
    try:
        interchange_id = await persist_parse_result(conn, filename, result)
    finally:
        await conn.close()

    return {
        "interchange_id": interchange_id,
        "parse_result": result.model_dump(),
    }
