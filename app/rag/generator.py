import json
from app.rag.llm_providers import get_provider
from app.utils.logger import rag_logger

SYSTEM_PROMPT = """You are an enterprise compliance expert for healthcare, banking, and insurance documents.

You will receive:
1. A detected error with its field, value, and rule violated
2. GraphRAG context: the relevant business rule, its parent regulation, and related fields
3. Few-shot examples: previously approved human fixes for similar errors

Use the few-shot examples to calibrate your recommendation.

Return ONLY this JSON:
{
  "explanation": "plain English root cause (2-3 sentences)",
  "regulation_cited": "exact regulation name and section",
  "fix_action": "specific corrective action",
  "suggested_value": "the corrected field value if applicable, else null",
  "confidence": "high|medium|low"
}"""

USER_TEMPLATE = """FEW-SHOT EXAMPLES FROM HUMAN FEEDBACK:
{few_shot_examples}

GRAPHRAG CONTEXT:
Rule: {rule_name} — {rule_description}
Regulation: {regulation_name} ({standard})
Historical fixes for this rule: {historical_fixes}

ERROR:
Field: {field}, Value: "{value}", Rule: {rule_violated}

Generate the compliance report JSON now."""


def generate_explanation(
    field: str,
    value: str,
    rule_violated: str,
    graphrag_context: dict,
    few_shot_examples: list[dict]
) -> dict:
    """Generate LLM-powered root-cause explanation, regulation citation, and suggested fix."""
    provider = get_provider()
    
    # Extract GraphRAG context details
    rules = graphrag_context.get("rules", [])
    regulations = graphrag_context.get("regulations", [])
    historical_fixes = graphrag_context.get("historical_fixes", [])
    
    rule_name = rules[0]["name"] if rules else "General Compliance Rule"
    rule_description = rules[0]["description"] if rules else rule_violated
    
    reg_name = regulations[0]["name"] if regulations else "N/A"
    reg_standard = regulations[0]["standard"] if regulations else "N/A"
    reg_version = regulations[0].get("version", "")
    reg_full = f"{reg_name} v{reg_version}" if reg_version else reg_name
    
    # Format historical fixes
    fixes_str = ""
    for idx, fix in enumerate(historical_fixes, 1):
        original = fix.get("original_value", "")
        approved = fix.get("approved_fix", "")
        fixes_str += f"\n  {idx}. Original value '{original}' was corrected to '{approved}'"
    if not fixes_str:
        fixes_str = " None available."
        
    # Format few-shot examples
    examples_str = ""
    for idx, ex in enumerate(few_shot_examples, 1):
        examples_str += (
            f"\nExample {idx}:\n"
            f"  - Error Field: {ex.get('field')}\n"
            f"  - Violated Rule: {ex.get('rule_violated')}\n"
            f"  - Original Value: '{ex.get('original_value')}'\n"
            f"  - Approved Correction: '{ex.get('approved_fix')}'\n"
        )
    if not examples_str:
        examples_str = " None available."

    user_prompt = USER_TEMPLATE.format(
        few_shot_examples=examples_str,
        rule_name=rule_name,
        rule_description=rule_description,
        regulation_name=reg_full,
        standard=reg_standard,
        historical_fixes=fixes_str,
        field=field,
        value=value if value is not None else "N/A",
        rule_violated=rule_violated
    )

    rag_logger.info(f"Invoking LLM for field '{field}' with rule '{rule_name}'")
    
    try:
        raw_response = provider.generate(SYSTEM_PROMPT, user_prompt)
    except Exception as e:
        rag_logger.error(f"LLM generation failed: {e}")
        # Return fallback mock structure
        return {
            "explanation": f"Validation failed for field '{field}'. Rule violated: {rule_violated}.",
            "regulation_cited": reg_full,
            "fix_action": f"Verify and correct the '{field}' value.",
            "suggested_value": None,
            "confidence": "low"
        }

    # Clean and parse the JSON response
    try:
        clean_response = raw_response.strip()
        if clean_response.startswith("```json"):
            clean_response = clean_response[7:]
        if clean_response.endswith("```"):
            clean_response = clean_response[:-3]
        clean_response = clean_response.strip()

        parsed = json.loads(clean_response)
        return {
            "explanation": parsed.get("explanation", ""),
            "regulation_cited": parsed.get("regulation_cited", ""),
            "fix_action": parsed.get("fix_action", ""),
            "suggested_value": parsed.get("suggested_value"),
            "confidence": parsed.get("confidence", "medium")
        }
    except Exception as e:
        rag_logger.error(f"Failed to parse LLM response: {e}. Raw response: {raw_response}")
        # Try finding suggested value via simple heuristics or return fallback
        return {
            "explanation": f"LLM parsing error. Raw output: {raw_response}",
            "regulation_cited": reg_full,
            "fix_action": "Check document details manually.",
            "suggested_value": None,
            "confidence": "low"
        }
