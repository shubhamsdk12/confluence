import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres_models import ValidationJob, Document
from app.agents.parser_agent import parse_and_register
from app.agents.diagnosis_agent import diagnose_claim
from app.agents.triage_agent import triage_results
from app.agents.repair_agent import repair_claim
from app.agents.audit_agent import generate_audit_report
from app.utils.logger import pipeline_logger

async def process_document_pipeline(
    db: AsyncSession,
    file_content: bytes,
    filename: str
) -> dict:
    """Coordinate the Phase 2 multi-agent pipeline in sequence."""
    pipeline_logger.info(f"[Orchestrator] Beginning pipeline execution for: {filename}")
    
    # 1. PARSER AGENT
    claim_ir, doc_id = await parse_and_register(db, file_content, filename)
    
    # Get industry type from the registered document
    doc = await db.get(Document, doc_id)
    industry = doc.industry if doc else "healthcare"
    
    # 2. Initialize ValidationJob
    job_id = uuid.uuid4()
    job = ValidationJob(
        job_id=job_id,
        doc_id=doc_id,
        started_at=datetime.utcnow(),
        total_errors=0,
        compliance_score=100.0
    )
    db.add(job)
    await db.flush()
    
    # 3. DIAGNOSIS AGENT
    results, suggested_fixes = await diagnose_claim(
        db=db,
        claim_ir=claim_ir,
        doc_id=doc_id,
        job_id=job_id,
        industry=industry
    )
    
    # 4. TRIAGE AGENT
    results = await triage_results(
        db=db,
        results=results,
        suggested_fixes=suggested_fixes
    )
    
    # 5. REPAIR AGENT
    repaired_ir = await repair_claim(
        db=db,
        results=results,
        suggested_fixes=suggested_fixes,
        claim_ir=claim_ir
    )
    
    # 6. AUDIT AGENT
    report = await generate_audit_report(
        db=db,
        doc_id=doc_id,
        job_id=job_id,
        results=results,
        claim_ir=repaired_ir
    )
    
    # 7. Update and complete ValidationJob details
    job.completed_at = datetime.utcnow()
    job.total_errors = len(results)
    job.compliance_score = report.compliance_score
    
    # Update Document status if all critical errors are resolved (or if 100% compliant)
    if report.compliance_score == 100.0:
        doc.status = "certified"
    elif sum(1 for r in results if r.status == "auto_fixed") > 0:
        doc.status = "repaired"
    else:
        doc.status = "validated"

    await db.flush()
    pipeline_logger.info(f"[Orchestrator] Completed pipeline execution. Job ID: {job_id}, Score: {job.compliance_score}%")
    
    # 8. Return formatted report for REST API response
    errors_list = []
    for r in results:
        # Check if there is an associated suggested fix or repair history entry
        sug_fix = suggested_fixes.get(r.result_id, "")
        errors_list.append({
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
        "status": doc.status,
        "filename": filename,
        "doc_id": str(doc_id),
        "job_id": str(job_id),
        "compliance_score": job.compliance_score,
        "total_errors": job.total_errors,
        "errors": errors_list,
        "summary": f"Validation complete. Score: {job.compliance_score}%. Total errors: {job.total_errors}."
    }
