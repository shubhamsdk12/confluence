import uuid
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres_models import ValidationResult, RepairHistory
from app.ir.models import ClaimIR
from app.utils.logger import pipeline_logger

async def repair_claim(
    db: AsyncSession,
    results: list[ValidationResult],
    suggested_fixes: dict[uuid.UUID, str],
    claim_ir: ClaimIR
) -> ClaimIR:
    """Apply safe fixes automatically, log repair history entries, and mark risky fixes as pending."""
    pipeline_logger.info("[Repair Agent] Executing claim repair process...")
    
    for result in results:
        suggested_val = suggested_fixes.get(result.result_id)
        
        # Skip if no fix is suggested by the LLM / rules
        if not suggested_val:
            continue
            
        if result.triage_category == "safe_fix":
            pipeline_logger.info(f"[Repair Agent] Applying safe fix for field '{result.field}': '{result.value}' -> '{suggested_val}'")
            
            # Apply the fix directly on ClaimIR
            field_path = result.field.split(".")
            if len(field_path) == 1:
                # Top level fields: claim_id, service_date, total_charge
                if hasattr(claim_ir, field_path[0]):
                    # If total_charge, convert to float
                    if field_path[0] == "total_charge":
                        try:
                            setattr(claim_ir, field_path[0], float(suggested_val))
                        except Exception:
                            pass
                    else:
                        setattr(claim_ir, field_path[0], suggested_val)
            elif len(field_path) == 2:
                # Subfields: provider.npi, patient.id, etc.
                obj = getattr(claim_ir, field_path[0], None)
                if obj and hasattr(obj, field_path[1]):
                    setattr(obj, field_path[1], suggested_val)

            # Create RepairHistory log for automated fix
            repair = RepairHistory(
                repair_id=uuid.uuid4(),
                result_id=result.result_id,
                original_value=result.value,
                suggested_fix=suggested_val,
                fix_type="safe",
                human_decision="approved",
                decided_at=datetime.utcnow(),
                decided_by="auto_repair_agent"
            )
            db.add(repair)
            
            # Mark validation result as auto_fixed
            result.status = "auto_fixed"
            
        elif result.triage_category == "risky_fix":
            pipeline_logger.info(f"[Repair Agent] Storing risky fix for field '{result.field}' for human review.")
            
            # Create RepairHistory log awaiting human triage decision
            repair = RepairHistory(
                repair_id=uuid.uuid4(),
                result_id=result.result_id,
                original_value=result.value,
                suggested_fix=suggested_val,
                fix_type="risky",
                human_decision=None,
                decided_at=None,
                decided_by=None
            )
            db.add(repair)
            
            # Mark validation result as pending (awaits human)
            result.status = "pending"

    await db.flush()
    pipeline_logger.info("[Repair Agent] Repair checks finished.")
    return claim_ir
