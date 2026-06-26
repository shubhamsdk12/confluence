from sqlalchemy.ext.asyncio import AsyncSession
from app.db.postgres_models import ValidationResult
from app.utils.logger import pipeline_logger

def classify_triage(result: ValidationResult) -> str:
    """Classify the triage category of a validation result according to safety guidelines."""
    field = (result.field or "").lower()
    rule = (result.rule_violated or "").lower()
    
    # 1. Risky fixes: NPI, duplicate check, financial changes, ID changes
    if "npi" in field or "npi" in rule:
        return "risky_fix"
    elif "duplicate" in rule or "claim_id" in field:
        return "risky_fix"
    elif "charge" in field or "amount" in field or "amount" in rule:
        return "risky_fix"
    elif "future" in rule or "temporal" in rule:
        return "risky_fix"
        
    # 2. Safe fixes: formatting, spaces, date normalizations, padding
    elif "space" in rule or "padding" in rule or "format" in rule:
        return "safe_fix"
    elif "date" in field:
        return "safe_fix"
        
    # 3. Manual checks: missing fields, diagnosis codes, procedure codes (anything ambiguous)
    else:
        return "manual"

async def triage_results(
    db: AsyncSession,
    results: list[ValidationResult],
    suggested_fixes: dict
) -> list[ValidationResult]:
    """Triage and categorize validation results, assign suggested fixes, and write to PostgreSQL."""
    pipeline_logger.info(f"[Triage Agent] Classifying {len(results)} validation results...")
    
    for result in results:
        # Determine category
        category = classify_triage(result)
        result.triage_category = category
        
        # If it's a safe fix and we don't have an LLM suggested value yet, we can try to guess a default or keep null
        # In our case, the diagnosis agent query to LLM produces suggested_value, which is passed in suggested_fixes.
        
        db.add(result)
        
    await db.flush()
    pipeline_logger.info("[Triage Agent] All validation results triaged and persisted.")
    return results
