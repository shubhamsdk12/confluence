import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres_models import ValidationResult, AuditReport, RepairHistory
from app.ir.models import ClaimIR
from app.utils.logger import pipeline_logger

async def generate_audit_report(
    db: AsyncSession,
    doc_id: uuid.UUID,
    job_id: uuid.UUID,
    results: list[ValidationResult],
    claim_ir: ClaimIR
) -> AuditReport:
    """Compile validation outcomes, calculate compliance score, and write AuditReport to PostgreSQL."""
    pipeline_logger.info(f"[Audit Agent] Generating audit report for Job ID: {job_id}")
    
    total_errors = len(results)
    auto_fixed = sum(1 for r in results if r.status == "auto_fixed")
    
    # Critical errors remaining (excluding auto-fixed ones)
    remaining_critical = sum(
        1 for r in results 
        if r.severity == "critical" and r.status not in ("auto_fixed", "approved")
    )
    
    # Define standard claim fields count
    total_fields = 10
    compliance_score = max(0.0, float(total_fields - remaining_critical) / total_fields * 100.0)
    
    # Build final payload dict representation of ClaimIR
    final_payload = {
        "claim_id": claim_ir.claim_id,
        "patient": {
            "id": claim_ir.patient.id,
            "name": claim_ir.patient.name,
            "dob": claim_ir.patient.dob,
            "member_id": claim_ir.patient.member_id
        },
        "provider": {
            "npi": claim_ir.provider.npi,
            "name": claim_ir.provider.name,
            "taxonomy_code": claim_ir.provider.taxonomy_code
        },
        "service_date": claim_ir.service_date,
        "total_charge": claim_ir.total_charge,
        "diagnosis_codes": claim_ir.diagnosis_codes,
        "procedure_codes": claim_ir.procedure_codes
    }

    # If score is 100, we can auto-certify, else certified starts False
    certified = (compliance_score == 100.0)

    report = AuditReport(
        report_id=uuid.uuid4(),
        doc_id=doc_id,
        job_id=job_id,
        compliance_score=compliance_score,
        total_errors=total_errors,
        auto_fixed=auto_fixed,
        human_approved=0,
        human_rejected=0,
        certified=certified,
        generated_at=datetime.utcnow(),
        final_payload=final_payload
    )

    db.add(report)
    await db.flush()
    
    pipeline_logger.info(f"[Audit Agent] Generated Audit Report with compliance score {compliance_score}% (certified={certified}).")
    return report
