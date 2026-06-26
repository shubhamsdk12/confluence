from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import uuid
from app.db.postgres import get_db
from app.db.postgres_models import AuditReport, Document

router = APIRouter()

@router.get("/audit/{job_id}")
async def get_audit(job_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch the AuditReport details for a specific validation job."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")
        
    stmt = select(AuditReport).where(AuditReport.job_id == job_uuid)
    res = await db.execute(stmt)
    report = res.scalars().first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Audit report not found.")
        
    return {
        "report_id": str(report.report_id),
        "doc_id": str(report.doc_id),
        "job_id": str(report.job_id),
        "compliance_score": report.compliance_score,
        "total_errors": report.total_errors,
        "auto_fixed": report.auto_fixed,
        "human_approved": report.human_approved,
        "human_rejected": report.human_rejected,
        "certified": report.certified,
        "generated_at": report.generated_at.isoformat(),
        "final_payload": report.final_payload
    }

@router.get("/audit/{job_id}/certify")
async def certify_audit(job_id: str, db: AsyncSession = Depends(get_db)):
    """Mark the validation job's document as certified and return its final compliance payload."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")
        
    stmt = select(AuditReport).where(AuditReport.job_id == job_uuid)
    res = await db.execute(stmt)
    report = res.scalars().first()
    
    if not report:
        raise HTTPException(status_code=404, detail="Audit report not found.")
        
    # Mark AuditReport as certified
    report.certified = True
    
    # Mark Document as certified
    doc = await db.get(Document, report.doc_id)
    if doc:
        doc.status = "certified"
        
    await db.flush()
    pipeline_logger_info = f"[Audit API] Certified Job ID {job_id} successfully."
    
    return {
        "message": "certified",
        "doc_id": str(report.doc_id),
        "certified": True,
        "final_payload": report.final_payload
    }
