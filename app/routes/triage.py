from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
import uuid
from datetime import datetime
from app.db.postgres import get_db
from app.db.postgres_models import (
    ValidationResult,
    RepairHistory,
    ValidationJob,
    Document,
    AuditReport,
    HumanFeedbackLog
)
from app.utils.logger import pipeline_logger

router = APIRouter()


@router.get("/triage/risky")
async def get_risky_triage(db: AsyncSession = Depends(get_db)):
    """Fetch all pending risky_fix items for human review."""
    stmt = (
        select(ValidationResult)
        .where(
            ValidationResult.triage_category == "risky_fix",
            ValidationResult.status == "pending"
        )
        .options(selectinload(ValidationResult.repair_history))
    )
    res = await db.execute(stmt)
    results = res.scalars().all()
    
    triage_cards = []
    for r in results:
        suggested_fix = ""
        if r.repair_history:
            suggested_fix = r.repair_history[0].suggested_fix or ""
            
        triage_cards.append({
            "result_id": str(r.result_id),
            "field": r.field,
            "original_value": r.value,
            "suggested_fix": suggested_fix,
            "llm_explanation": r.llm_explanation,
            "regulation_cited": r.regulation_cited or "N/A",
            "severity": r.severity
        })
        
    return triage_cards


@router.post("/triage/{result_id}/approve")
async def approve_fix(result_id: str, db: AsyncSession = Depends(get_db)):
    """Approve a suggested fix, updating validation result, repair history, final payload, and learning logs."""
    try:
        res_uuid = uuid.UUID(result_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")
        
    # Query ValidationResult with relationships
    stmt = (
        select(ValidationResult)
        .where(ValidationResult.result_id == res_uuid)
        .options(selectinload(ValidationResult.repair_history))
    )
    db_res = await db.execute(stmt)
    result = db_res.scalars().first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Validation result not found.")
        
    if result.status == "approved":
        return {"message": "Fix already approved.", "result_id": result_id}
        
    # Update ValidationResult status
    result.status = "approved"
    
    # Update RepairHistory
    suggested_val = ""
    if result.repair_history:
        repair = result.repair_history[0]
        repair.human_decision = "approved"
        repair.decided_at = datetime.utcnow()
        repair.decided_by = "human"
        suggested_val = repair.suggested_fix or ""
        
    # Fetch job, document and audit report to sync updates
    job = await db.get(ValidationJob, result.job_id)
    if not job:
        raise HTTPException(status_code=500, detail="Associated validation job not found.")
        
    doc = await db.get(Document, job.doc_id)
    industry = doc.industry if doc else "healthcare"
    
    # Write to HumanFeedbackLogs for continuous learning
    log = HumanFeedbackLog(
        log_id=uuid.uuid4(),
        error_type=result.error_type,
        field=result.field,
        rule_violated=result.rule_violated,
        original_value=result.value,
        approved_fix=suggested_val,
        feedback_at=datetime.utcnow(),
        industry=industry
    )
    db.add(log)
    
    # Update AuditReport payload and metrics
    audit_stmt = select(AuditReport).where(AuditReport.job_id == job.job_id)
    audit_res = await db.execute(audit_stmt)
    report = audit_res.scalars().first()
    
    if report:
        report.human_approved += 1
        
        # Apply fix to final_payload
        payload = report.final_payload or {}
        field_path = result.field.split(".")
        if len(field_path) == 1:
            payload[field_path[0]] = suggested_val
        elif len(field_path) == 2:
            obj = payload.get(field_path[0])
            if isinstance(obj, dict):
                obj[field_path[1]] = suggested_val
                payload[field_path[0]] = obj
        report.final_payload = payload
        
        # Recalculate compliance score
        # Query all results for the job to determine active errors
        all_results_stmt = select(ValidationResult).where(ValidationResult.job_id == job.job_id)
        all_res = await db.execute(all_results_stmt)
        all_results = all_res.scalars().all()
        
        remaining_critical = sum(
            1 for r in all_results
            if r.severity == "critical" and r.status not in ("auto_fixed", "approved")
        )
        
        total_fields = 10
        score = max(0.0, float(total_fields - remaining_critical) / total_fields * 100.0)
        report.compliance_score = score
        job.compliance_score = score
        
        if score == 100.0:
            report.certified = True
            if doc:
                doc.status = "certified"
                
    await db.flush()
    pipeline_logger.info(f"[Triage API] Approved result {result_id}. Continuous learning feed updated.")
    
    return {"message": "Fix approved and applied.", "result_id": result_id}


@router.post("/triage/{result_id}/reject")
async def reject_fix(result_id: str, db: AsyncSession = Depends(get_db)):
    """Reject a suggested fix, updating validation result status, repair history, and learning logs."""
    try:
        res_uuid = uuid.UUID(result_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid UUID format.")
        
    stmt = (
        select(ValidationResult)
        .where(ValidationResult.result_id == res_uuid)
        .options(selectinload(ValidationResult.repair_history))
    )
    db_res = await db.execute(stmt)
    result = db_res.scalars().first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Validation result not found.")
        
    if result.status == "rejected":
        return {"message": "Fix already rejected.", "result_id": result_id}
        
    result.status = "rejected"
    
    if result.repair_history:
        repair = result.repair_history[0]
        repair.human_decision = "rejected"
        repair.decided_at = datetime.utcnow()
        repair.decided_by = "human"
        
    # Fetch job and document
    job = await db.get(ValidationJob, result.job_id)
    doc = await db.get(Document, job.doc_id) if job else None
    industry = doc.industry if doc else "healthcare"
    
    # Write to HumanFeedbackLogs with approved_fix = null
    log = HumanFeedbackLog(
        log_id=uuid.uuid4(),
        error_type=result.error_type,
        field=result.field,
        rule_violated=result.rule_violated,
        original_value=result.value,
        approved_fix=None,
        feedback_at=datetime.utcnow(),
        industry=industry
    )
    db.add(log)
    
    # Increment human_rejected on AuditReport
    if job:
        audit_stmt = select(AuditReport).where(AuditReport.job_id == job.job_id)
        audit_res = await db.execute(audit_stmt)
        report = audit_res.scalars().first()
        if report:
            report.human_rejected += 1
            
    await db.flush()
    pipeline_logger.info(f"[Triage API] Rejected result {result_id}.")
    
    return {"message": "Fix rejected.", "result_id": result_id}
