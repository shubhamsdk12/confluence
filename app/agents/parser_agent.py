import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.parser.classifier import classify_format
from app.parser.edi_parser import parse_edi
from app.parser.json_parser import parse_json
from app.db.postgres_models import Document
from app.utils.logger import pipeline_logger
from app.ir.models import ClaimIR

async def parse_and_register(db: AsyncSession, file_content: bytes, filename: str) -> tuple[ClaimIR, uuid.UUID]:
    """Parse claim file content to ClaimIR, write a Document record to PostgreSQL, and return (ClaimIR, doc_id)."""
    pipeline_logger.info(f"[Parser Agent] Processing file: {filename}")
    
    content_str = file_content.decode("utf-8", errors="ignore")
    
    # 1. Detect format and parse
    fmt = classify_format(content_str)
    if fmt == "edi":
        claim_ir = parse_edi(content_str)
        industry = "healthcare"
    else:
        claim_ir = parse_json(content_str)
        # Determine industry (JSON claims are healthcare)
        industry = "healthcare"

    # Determine if it's banking (e.g. if fields match ISO 20022) or insurance/tax
    # For now, default to healthcare or detect based on file contents
    if "iban" in content_str.lower() or "bic" in content_str.lower() or "iso20022" in content_str.lower():
        industry = "banking"
    elif "gstin" in content_str.lower() or "gst" in content_str.lower():
        industry = "insurance"

    # 2. Write Document record to PostgreSQL
    doc_id = uuid.uuid4()
    doc = Document(
        doc_id=doc_id,
        filename=filename,
        industry=industry,
        status="pending",
        uploaded_by="system",
        upload_time=datetime.utcnow(),
        raw_content=content_str
    )
    
    db.add(doc)
    await db.flush() # Ensure doc_id is registered before committing later
    pipeline_logger.info(f"[Parser Agent] Registered Document ID {doc_id} with status pending.")
    
    return claim_ir, doc_id
