from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from app.db.postgres_models import HumanFeedbackLog
from app.utils.logger import pipeline_logger

async def get_few_shot_examples(db: AsyncSession, field: str, industry: str) -> list[dict]:
    """Retrieve up to 3 recent approved human fixes for similar errors to use as few-shot context."""
    pipeline_logger.info(f"[Learning Agent] Querying feedback logs for field='{field}', industry='{industry}'")
    try:
        stmt = (
            select(HumanFeedbackLog)
            .where(HumanFeedbackLog.field == field, HumanFeedbackLog.industry == industry)
            .order_by(desc(HumanFeedbackLog.feedback_at))
            .limit(3)
        )
        res = await db.execute(stmt)
        logs = res.scalars().all()
        
        examples = []
        for log in logs:
            examples.append({
                "field": log.field,
                "rule_violated": log.rule_violated,
                "original_value": log.original_value,
                "approved_fix": log.approved_fix
            })
            
        pipeline_logger.info(f"[Learning Agent] Found {len(examples)} feedback logs.")
        return examples
    except Exception as e:
        pipeline_logger.error(f"[Learning Agent] Error fetching feedback logs: {e}")
        return []
