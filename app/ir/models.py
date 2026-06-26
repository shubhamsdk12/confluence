from pydantic import BaseModel


class SegmentIR(BaseModel):
    segment_id: str          # e.g. "CLM", "NM1", "DTP"
    position: int
    fields: dict[str, str]   # field_name → value


class PatientIR(BaseModel):
    id: str
    name: str
    dob: str | None = None
    member_id: str | None = None


class ProviderIR(BaseModel):
    npi: str
    name: str
    taxonomy_code: str | None = None


class ClaimIR(BaseModel):
    claim_id: str
    patient: PatientIR
    provider: ProviderIR
    service_date: str
    total_charge: float
    diagnosis_codes: list[str]
    procedure_codes: list[str]
    segments: list[SegmentIR]
    raw_errors: list[str] = []   # structural parse errors


class ErrorIR(BaseModel):
    error_id: str
    error_type: str              # "structural" | "semantic" | "relational"
    field: str
    value: str
    rule_violated: str
    vector_context: str = ""     # retrieved rule text from ChromaDB
    graph_context: str = ""      # result of Cypher query
    llm_explanation: str = ""    # final plain-English explanation
    regulation_cited: str = ""   # cited regulation from LLM
    fix_action: str = ""         # recommended fix from LLM
    severity: str                # "critical" | "warning" | "info"
