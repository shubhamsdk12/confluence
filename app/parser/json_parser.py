import json
from app.ir.models import ClaimIR, PatientIR, ProviderIR
from app.utils.logger import parser_logger


def parse_json(content: str) -> ClaimIR:
    """Parse JSON claim format into ClaimIR."""
    parser_logger.info("Parsing JSON file content...")
    raw_errors = []

    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        parser_logger.error(f"Failed to parse JSON: {e}")
        return ClaimIR(
            claim_id="",
            patient=PatientIR(id="", name=""),
            provider=ProviderIR(npi="", name=""),
            service_date="",
            total_charge=0.0,
            diagnosis_codes=[],
            procedure_codes=[],
            segments=[],
            raw_errors=[f"Invalid JSON format: {str(e)}"],
        )

    claim_id = data.get("claim_id", "")
    if not claim_id:
        raw_errors.append("Missing mandatory field: claim_id")

    patient_data = data.get("patient", {})
    patient_id = patient_data.get("id", "")
    patient_name = patient_data.get("name", "")
    patient_dob = patient_data.get("dob")
    patient_member_id = patient_data.get("member_id", patient_id)

    if not patient_id:
        raw_errors.append("Missing mandatory field: patient.id")
    if not patient_name:
        raw_errors.append("Missing mandatory field: patient.name")

    provider_data = data.get("provider", {})
    provider_npi = provider_data.get("npi", "")
    provider_name = provider_data.get("name", "")
    provider_taxonomy = provider_data.get("taxonomy_code")

    if not provider_npi:
        raw_errors.append("Missing mandatory field: provider.npi")
    if not provider_name:
        raw_errors.append("Missing mandatory field: provider.name")

    service_date = data.get("service_date", "")
    if not service_date:
        raw_errors.append("Missing mandatory field: service_date")

    total_charge_raw = data.get("total_charge", 0.0)
    try:
        total_charge = float(total_charge_raw)
    except (ValueError, TypeError):
        total_charge = 0.0
        raw_errors.append(f"Invalid total_charge value: {total_charge_raw}")

    diagnosis_codes = data.get("diagnosis_codes", [])
    if not isinstance(diagnosis_codes, list):
        diagnosis_codes = []
        raw_errors.append("diagnosis_codes must be a list")
    elif not diagnosis_codes:
        raw_errors.append(
            "Missing mandatory field: diagnosis_codes must not be empty"
        )

    procedure_codes = data.get("procedure_codes", [])
    if not isinstance(procedure_codes, list):
        procedure_codes = []
        raw_errors.append("procedure_codes must be a list")
    elif not procedure_codes:
        raw_errors.append(
            "Missing mandatory field: procedure_codes must not be empty"
        )

    # In JSON claims, there are no EDI segments, but we return an empty list
    segments = []

    parser_logger.info(
        f"Parsed JSON claim {claim_id} with {len(raw_errors)} raw structural errors."
    )

    return ClaimIR(
        claim_id=claim_id,
        patient=PatientIR(
            id=patient_id,
            name=patient_name,
            dob=patient_dob,
            member_id=patient_member_id,
        ),
        provider=ProviderIR(
            npi=provider_npi, name=provider_name, taxonomy_code=provider_taxonomy
        ),
        service_date=service_date,
        total_charge=total_charge,
        diagnosis_codes=diagnosis_codes,
        procedure_codes=procedure_codes,
        segments=segments,
        raw_errors=raw_errors,
    )
