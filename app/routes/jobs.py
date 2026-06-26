from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid
from app.db.postgres import get_db
from app.db.postgres_models import ValidationJob, ValidationResult, RepairHistory

router = APIRouter()

@router.get("/jobs/{job_id}")
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    """Fetch ValidationJob details along with all related ValidationResults and suggested fixes."""
    try:
        job_uuid = uuid.UUID(job_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")
        
    stmt = (
        select(ValidationJob)
        .where(ValidationJob.job_id == job_uuid)
        .options(selectinload(ValidationJob.results).selectinload(ValidationResult.repair_history))
    )
    res = await db.execute(stmt)
    job = res.scalars().first()
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
        
    results_list = []
    for r in job.results:
        sug_fix = ""
        # Get suggested fix from repair history if present
        if r.repair_history:
            sug_fix = r.repair_history[0].suggested_fix or ""
            
        results_list.append({
            "result_id": str(r.result_id),
            "error_type": r.error_type,
            "field": r.field,
            "value": r.value,
            "rule_violated": r.rule_violated,
            "llm_explanation": r.llm_explanation,
            "severity": r.severity,
            "triage_category": r.triage_category,
            "status": r.status,
            "suggested_fix": sug_fix
        })
        
    return {
        "job_id": str(job.job_id),
        "doc_id": str(job.doc_id),
        "started_at": job.started_at.isoformat(),
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "total_errors": job.total_errors,
        "compliance_score": job.compliance_score,
        "errors": results_list
    }
