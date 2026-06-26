import uuid
from app.knowledge.graph_store import graph_store
from app.ir.models import ErrorIR
from app.utils.logger import rag_logger


def run_graph_validation(
    claim_id: str, provider_npi: str, service_date: str
) -> list[ErrorIR]:
    """Run all 3 graph-based Cypher validators and return a list of ErrorIRs for any failures."""
    rag_logger.info(f"Running graph validations for claim ID: {claim_id}")
    errors = []

    # 1. Duplicate claim validation
    dup_res = graph_store.validate_duplicate_claim(claim_id)
    if not dup_res["passed"]:
        errors.append(
            ErrorIR(
                error_id=f"ERR_{uuid.uuid4().hex[:6].upper()}",
                error_type="relational",
                field="claim_id",
                value=claim_id,
                rule_violated="Duplicate claim submission detected.",
                graph_context=dup_res["detail"],
                vector_context="",
                llm_explanation="",
                severity="critical",
            )
        )

    # 2. Provider NPI validation
    npi_res = graph_store.validate_provider_npi(provider_npi)
    if not npi_res["passed"]:
        errors.append(
            ErrorIR(
                error_id=f"ERR_{uuid.uuid4().hex[:6].upper()}",
                error_type="structural",
                field="provider.npi",
                value=provider_npi,
                rule_violated="NPI must be exactly 10 digits.",
                graph_context=npi_res["detail"],
                vector_context="",
                llm_explanation="",
                severity="critical",
            )
        )

    # 3. Service date validation
    date_res = graph_store.validate_service_date(claim_id)
    if not date_res["passed"]:
        errors.append(
            ErrorIR(
                error_id=f"ERR_{uuid.uuid4().hex[:6].upper()}",
                error_type="semantic",
                field="service_date",
                value=service_date,
                rule_violated="Service date cannot be in the future.",
                graph_context=date_res["detail"],
                vector_context="",
                llm_explanation="",
                severity="warning",
            )
        )

    return errors
