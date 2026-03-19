"""
AI Explainer — synthesizes SQL facts + RAG context into plain-English explanations.

Includes PHI masking per .cursorrules §3: Privacy by Design.
"""
from __future__ import annotations

import os
import re
from typing import Any

from ai.retriever import retrieve_context
from parser.models import ValidationError

# ---------------------------------------------------------------------------
# PHI Masking
# ---------------------------------------------------------------------------

_PHI_PATTERNS = [
    # SSN patterns (XXX-XX-XXXX or 9 digits)
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "[SSN]"),
    (re.compile(r"\b\d{9}\b(?!\d)"), "[SSN_OR_ID]"),
    # Date of birth patterns (various formats)
    (re.compile(r"\b(19|20)\d{2}(0[1-9]|1[0-2])(0[1-9]|[12]\d|3[01])\b"), "[DATE]"),
    # Member IDs (common patterns)
    (re.compile(r"\bMEMBER\d+\b", re.IGNORECASE), "[MEMBER_ID]"),
    (re.compile(r"\bMCARE\d+\b", re.IGNORECASE), "[MEMBER_ID]"),
    # Addresses
    (re.compile(r"\b\d+\s+[A-Z][A-Za-z]+\s+(STREET|ST|AVENUE|AVE|DRIVE|DR|ROAD|RD|BLVD|LANE|LN)\b", re.IGNORECASE), "[ADDRESS]"),
]

# Names to mask — these would come from the parsed data in production
_NAME_PATTERN = re.compile(
    r"\b(DOE|SMITH|JONES|WILLIAMS|JOHNSON|BROWN|DAVIS|MILLER|WILSON|MOORE|ALICE|BOB|JOHN|JANE|MARY|ROBERT)\b",
    re.IGNORECASE,
)


def mask_phi(text: str) -> str:
    """
    Replace known PHI patterns in text before sending to external LLMs.

    Per .cursorrules §3: Never send raw PHI to external LLM APIs
    without sanitization or explicit masking.
    """
    masked = text
    for pattern, replacement in _PHI_PATTERNS:
        masked = pattern.sub(replacement, masked)
    masked = _NAME_PATTERN.sub("[PATIENT]", masked)
    return masked


# ---------------------------------------------------------------------------
# Explainer
# ---------------------------------------------------------------------------

def explain_error(
    error: ValidationError,
    sql_context: str = "",
) -> dict[str, Any]:
    """
    Generate a plain-English explanation for a validation error.

    Combines:
      1. The error details (deterministic, from SQL)
      2. RAG-retrieved regulatory context (from ChromaDB)

    For hackathon: returns structured explanation without calling an LLM.
    In production, this would construct a prompt and call the LLM.

    Args:
        error: The ValidationError to explain.
        sql_context: Additional context from the SQL query results.

    Returns:
        Dict with: plain_english, regulatory_context, suggested_fix, sources[].
    """
    # Build query for RAG retrieval
    query_parts = [error.message]
    if error.code:
        query_parts.append(error.code)
    if error.segment_id:
        query_parts.append(f"segment {error.segment_id}")
    query = " ".join(query_parts)

    # Retrieve context from ChromaDB
    rag_results = retrieve_context(query, n_results=5)

    # Build explanation (deterministic for hackathon — no LLM call needed)
    sources = [r["metadata"].get("source", "unknown") for r in rag_results]
    context_texts = [r["text"] for r in rag_results]

    # Construct structured response
    explanation: dict[str, Any] = {
        "error_code": error.code,
        "snip_level": error.snip_level,
        "severity": error.severity.value,
        "plain_english": _build_plain_english(error, context_texts),
        "regulatory_context": context_texts[:3],
        "suggested_fix": error.suggestion or "Review the flagged segment and consult HIPAA 5010 guidelines.",
        "sources": list(set(sources)),
        "sql_facts": sql_context,
    }

    return explanation


def _build_plain_english(error: ValidationError, context: list[str]) -> str:
    """Build a human-readable explanation from the error and context."""
    parts = [f"**{error.severity.value.upper()}** (SNIP Level {error.snip_level}): {error.message}"]

    if context:
        parts.append("\n**Regulatory Context:**")
        for ctx in context[:2]:
            # Mask any PHI in context before displaying
            parts.append(f"- {mask_phi(ctx[:200])}")

    if error.suggestion:
        parts.append(f"\n**Suggested Fix:** {error.suggestion}")

    return "\n".join(parts)


def explain_errors_batch(
    errors: list[ValidationError],
) -> list[dict[str, Any]]:
    """Explain multiple errors in batch."""
    return [explain_error(e) for e in errors]
