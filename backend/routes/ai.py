"""
AI Intelligence API routes — POST /api/explain, /api/chat, /api/fix

Provides AI-powered error explanations, freeform chat about EDI files,
and automated fix suggestions using RAG retrieval from ChromaDB.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai.explainer import explain_error, explain_errors_batch, mask_phi
from ai.retriever import retrieve_context, retrieve_for_error_code
from parser.models import ValidationError, Severity

router = APIRouter()


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------

class ExplainRequest(BaseModel):
    """Request to explain a single validation error."""
    segment_id: str = ""
    element_position: int | None = None
    loop_id: str = ""
    snip_level: int = Field(..., ge=1, le=3)
    severity: str = "error"
    code: str = ""
    message: str = ""
    suggestion: str = ""


class ExplainBatchRequest(BaseModel):
    """Request to explain multiple validation errors."""
    errors: list[ExplainRequest]


class ChatRequest(BaseModel):
    """Freeform question about an EDI file or HIPAA regulations."""
    question: str
    context: str = ""  # Optional: raw EDI content or prior context


class FixRequest(BaseModel):
    """Request to fix a specific validation error."""
    segment_id: str = ""
    element_position: int | None = None
    snip_level: int = Field(..., ge=1, le=3)
    code: str = ""
    message: str = ""
    raw_segment: str = ""  # The original segment text


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post("/explain")
async def explain_validation_error(req: ExplainRequest):
    """
    Explain a single validation error in plain English using RAG context.

    Returns: plain_english explanation, regulatory context, suggested fix, sources.
    """
    try:
        error = ValidationError(
            segment_id=req.segment_id,
            element_position=req.element_position,
            loop_id=req.loop_id,
            snip_level=req.snip_level,
            severity=Severity(req.severity),
            code=req.code,
            message=req.message,
            suggestion=req.suggestion,
        )
        result = explain_error(error)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/explain/batch")
async def explain_batch(req: ExplainBatchRequest):
    """Explain multiple validation errors in batch."""
    try:
        errors = [
            ValidationError(
                segment_id=r.segment_id,
                element_position=r.element_position,
                loop_id=r.loop_id,
                snip_level=r.snip_level,
                severity=Severity(r.severity),
                code=r.code,
                message=r.message,
                suggestion=r.suggestion,
            )
            for r in req.errors
        ]
        results = explain_errors_batch(errors)
        return {"explanations": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat")
async def chat(req: ChatRequest):
    """
    Freeform question about EDI files, HIPAA regulations, or validation rules.

    Uses RAG retrieval to provide context-aware answers.
    """
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    try:
        # Mask any PHI in the question before processing
        safe_question = mask_phi(req.question)

        # Retrieve relevant context from the knowledge base
        context_results = retrieve_context(safe_question, n_results=5)

        context_texts = [r["text"] for r in context_results]
        sources = list(set(r["metadata"].get("source", "unknown") for r in context_results))

        # Build response (deterministic for hackathon — no external LLM call)
        answer_parts = [f"**Question:** {safe_question}\n"]

        if context_texts:
            answer_parts.append("**Relevant Information:**\n")
            for i, ctx in enumerate(context_texts[:3], 1):
                answer_parts.append(f"{i}. {mask_phi(ctx[:300])}\n")
        else:
            answer_parts.append(
                "No directly relevant information was found in the knowledge base. "
                "Please consult the HIPAA 5010 Implementation Guide for detailed guidance."
            )

        return {
            "answer": "\n".join(answer_parts),
            "sources": sources,
            "context_count": len(context_results),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/fix")
async def suggest_fix(req: FixRequest):
    """
    Suggest a fix for a specific validation error.

    Analyzes the error and original segment to propose a corrected value.
    """
    if not req.code and not req.message:
        raise HTTPException(
            status_code=400,
            detail="Either error code or message must be provided",
        )

    try:
        # Build a ValidationError for the explainer
        error = ValidationError(
            segment_id=req.segment_id,
            element_position=req.element_position,
            snip_level=req.snip_level,
            severity=Severity.ERROR,
            code=req.code,
            message=req.message,
        )

        # Get explanation with fix suggestion
        explanation = explain_error(error)

        # Build fix response
        fix_result = {
            "error_code": req.code,
            "original_segment": mask_phi(req.raw_segment),
            "suggested_fix": explanation.get("suggested_fix", ""),
            "explanation": explanation.get("plain_english", ""),
            "confidence": "medium",  # Deterministic fixes have medium confidence
            "sources": explanation.get("sources", []),
        }

        # Add specific fix suggestions based on error type
        if "SNIP1" in req.code:
            fix_result["fix_type"] = "envelope"
            fix_result["confidence"] = "high"
        elif "SNIP2" in req.code:
            fix_result["fix_type"] = "compliance"
        elif "SNIP3" in req.code:
            fix_result["fix_type"] = "balancing"
            fix_result["confidence"] = "high"

        return fix_result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/lookup/carc/{code}")
async def lookup_carc(code: str):
    """Look up a CARC (Claim Adjustment Reason Code) from the knowledge base."""
    results = retrieve_for_error_code(code, code_type="CARC")
    return {
        "code": code,
        "code_type": "CARC",
        "results": results,
    }


@router.post("/lookup/rarc/{code}")
async def lookup_rarc(code: str):
    """Look up a RARC (Remittance Advice Remark Code) from the knowledge base."""
    results = retrieve_for_error_code(code, code_type="RARC")
    return {
        "code": code,
        "code_type": "RARC",
        "results": results,
    }
