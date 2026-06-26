import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from app.ir.models import ClaimIR
from app.db.postgres_models import ValidationResult
from app.knowledge.graph_store import graph_store
from app.rag.graph_rag import graphrag_retrieve
from app.agents.learning_agent import get_few_shot_examples
from app.rag.generator import generate_explanation
from app.utils.logger import pipeline_logger

async def diagnose_claim(
    db: AsyncSession,
    claim_ir: ClaimIR,
    doc_id: uuid.UUID,
    job_id: uuid.UUID,
    industry: str
) -> tuple[list[ValidationResult], dict[uuid.UUID, str]]:
    """Execute structural validations and graph-based validations, call GraphRAG, and generate explanations."""
    pipeline_logger.info(f"[Diagnosis Agent] Executing validations for Claim ID: {claim_ir.claim_id or 'UNKNOWN'}")
    
    validation_results = []
    suggested_fixes = {}  # result_id -> suggested_value

    # Helper function to process an error through GraphRAG and LLM
    async def process_error(field: str, value: str, rule_violated: str, err_type: str, severity: str = "critical") -> ValidationResult:
        result_id = uuid.uuid4()
        
        # 1. Fetch Neo4j GraphRAG context
        context = graphrag_retrieve(rule_violated)
        
        # 2. Get few-shot learning examples
        examples = await get_few_shot_examples(db, field, industry)
        
        # 3. Call LLM for explanation and suggested fix
        llm_res = generate_explanation(field, value, rule_violated, context, examples)
        
        # 4. Link claim node to violated BusinessRule node in Neo4j if rule matches
        if context.get("rules") and claim_ir.claim_id:
            rule_node_id = context["rules"][0]["rule_id"]
            graph_store.link_claim_violation(claim_ir.claim_id, rule_node_id)

        # 5. Store suggestion
        sug_val = llm_res.get("suggested_value")
        if sug_val is not None:
            suggested_fixes[result_id] = str(sug_val)
        
        return ValidationResult(
            result_id=result_id,
            job_id=job_id,
            error_type=err_type,
            field=field,
            value=value or "",
            rule_violated=rule_violated,
            llm_explanation=llm_res.get("explanation"),
            regulation_cited=llm_res.get("regulation_cited"),
            severity=severity,
            triage_category="manual",  # Will be classified by Triage Agent
            status="pending"
        )

    # --- Category A: Structural errors from Parser ---
    for err_msg in claim_ir.raw_errors:
        field = "document"
        rule_violated = err_msg
        severity = "critical"
        value = ""

        err_msg_lower = err_msg.lower()
        if "clm" in err_msg_lower or "claim id" in err_msg_lower:
            field = "claim_id"
            rule_violated = "HIPAA X12 837P: CLM segment is mandatory. Missing CLM constitutes a fatal structural error."
            value = claim_ir.claim_id
        elif "patient" in err_msg_lower:
            field = "patient.id"
            rule_violated = "Patient identifier is mandatory (NM1*QC segment)."
            value = claim_ir.patient.id
        elif "provider" in err_msg_lower or "npi" in err_msg_lower:
            field = "provider.npi"
            rule_violated = "NPI (National Provider Identifier) must be a 10-digit numeric string. Invalid NPI causes claim rejection."
            value = claim_ir.provider.npi
        elif "service date" in err_msg_lower:
            field = "service_date"
            rule_violated = "Service date (DTP*472) must be present."
            value = claim_ir.service_date
        elif "diagnosis" in err_msg_lower:
            field = "diagnosis_codes"
            rule_violated = "ICD-10 diagnosis codes must be present on every professional claim. Minimum one HI segment required."
            value = ",".join(claim_ir.diagnosis_codes)
        elif "procedure" in err_msg_lower:
            field = "procedure_codes"
            rule_violated = "Procedure code must be a valid CPT-4 or HCPCS Level II code. Minimum one SV1 segment required."
            value = ",".join(claim_ir.procedure_codes)

        res = await process_error(field, value, rule_violated, "structural", severity)
        validation_results.append(res)

    # --- Category B: Relational / Temporal errors from Neo4j ---
    if claim_ir.claim_id:
        # Load claims node and relations into graph DB
        graph_store.create_claim_graph(claim_ir)
        
        # 1. Duplicate claim check
        dup_res = graph_store.validate_duplicate_claim(claim_ir.claim_id)
        if not dup_res.get("passed", True):
            res = await process_error(
                field="claim_id",
                value=claim_ir.claim_id,
                rule_violated="Duplicate claim validation. A claim ID cannot be submitted multiple times.",
                err_type="relational",
                severity="critical"
            )
            validation_results.append(res)
            
        # 2. Provider NPI validation check
        if claim_ir.provider.npi:
            npi_res = graph_store.validate_provider_npi(claim_ir.provider.npi)
            if not npi_res.get("passed", True):
                res = await process_error(
                    field="provider.npi",
                    value=claim_ir.provider.npi,
                    rule_violated="NPI must be exactly 10 digits.",
                    err_type="relational",
                    severity="critical"
                )
                validation_results.append(res)
                
        # 3. Future service date validation check
        if claim_ir.service_date:
            date_res = graph_store.validate_service_date(claim_ir.claim_id, claim_ir.service_date)
            if not date_res.get("passed", True):
                res = await process_error(
                    field="service_date",
                    value=claim_ir.service_date,
                    rule_violated="Future service date is prohibited. Service date must be on or before the upload date.",
                    err_type="relational",
                    severity="critical"
                )
                validation_results.append(res)

    pipeline_logger.info(f"[Diagnosis Agent] Diagnosed {len(validation_results)} total errors.")
    return validation_results, suggested_fixes
