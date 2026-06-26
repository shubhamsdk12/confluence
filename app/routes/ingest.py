from fastapi import APIRouter, UploadFile, File, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres import get_db
from app.orchestrator import process_document_pipeline
from app.utils.logger import pipeline_logger

router = APIRouter()


@router.post("/ingest")
async def ingest_claim(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """Accept claim file upload, run multi-agent validations, persist results in PostgreSQL, and return report."""
    pipeline_logger.info(f"API upload received for file: {file.filename}")
    content = await file.read()
    
    # Run pipeline with database session
    report = await process_document_pipeline(db, content, file.filename)
    return report
