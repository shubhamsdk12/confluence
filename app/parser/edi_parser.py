from app.ir.models import ClaimIR, SegmentIR, PatientIR, ProviderIR
from app.utils.logger import parser_logger


def parse_edi(content: str) -> ClaimIR:
    """Parse EDI X12 837P claims file into ClaimIR."""
    parser_logger.info("Parsing EDI file content...")
    raw_errors = []
    segments_ir = []

    # Default fields
    claim_id = ""
    total_charge = 0.0
    patient_id = ""
    patient_name = ""
    patient_dob = None
    patient_member_id = None
    provider_npi = ""
    provider_name = ""
    provider_taxonomy = None
    service_date = ""
    diagnosis_codes = []
    procedure_codes = []

    # Clean content and split into segments
    content_clean = content.replace("\n", "").replace("\r", "")
    raw_segments = content_clean.split("~")

    position = 0
    for raw_seg in raw_segments:
        raw_seg = raw_seg.strip()
        if not raw_seg:
            continue
        position += 1
        elements = raw_seg.split("*")
        seg_id = elements[0]

        # Map fields for SegmentIR
        fields = {}
        for idx, val in enumerate(elements[1:], 1):
            fields[f"{seg_id}{idx:02d}"] = val

        segments_ir.append(
            SegmentIR(segment_id=seg_id, position=position, fields=fields)
        )

        if seg_id == "CLM":
            # CLM*claim_id*total_charge***place_of_service
            if len(elements) > 1:
                claim_id = elements[1]
            else:
                raw_errors.append("CLM segment missing Claim ID.")

            if len(elements) > 2:
                try:
                    total_charge = float(elements[2])
                except ValueError:
                    raw_errors.append(
                        f"CLM segment has invalid charge amount: {elements[2]}"
                    )
            else:
                raw_errors.append("CLM segment missing Total Charge.")

        elif seg_id == "NM1":
            # NM1*QC*1*PATIENT_LAST*PATIENT_FIRST****MI*MEMBER_ID  (Loop 2010BA)
            # NM1*85*2*PROVIDER_NAME****XX*NPI                    (Loop 2010AA)
            if len(elements) > 1:
                loop_type = elements[1]
                if loop_type == "QC":  # Patient
                    last_name = elements[3] if len(elements) > 3 else ""
                    first_name = elements[4] if len(elements) > 4 else ""
                    patient_name = (
                        f"{first_name} {last_name}".strip()
                        if first_name
                        else last_name
                    )
                    patient_id = elements[9] if len(elements) > 9 else ""
                    patient_member_id = patient_id
                elif loop_type == "85":  # Billing Provider
                    provider_name = elements[3] if len(elements) > 3 else ""
                    provider_npi = elements[9] if len(elements) > 9 else ""
            else:
                raw_errors.append("NM1 segment missing Loop Type.")

        elif seg_id == "DTP":
            # DTP*472*D8*service_date
            if len(elements) > 1 and elements[1] == "472":
                if len(elements) > 3:
                    service_date = elements[3]
                else:
                    raw_errors.append("DTP segment missing Service Date value.")

        elif seg_id == "HI":
            # HI*ABK:diagnosis_code1*ABK:diagnosis_code2
            for elem in elements[1:]:
                if not elem:
                    continue
                # Some EDI files might separate qualifier and code with ':'
                if ":" in elem:
                    code = elem.split(":")[1]
                else:
                    code = elem
                if code:
                    diagnosis_codes.append(code)

        elif seg_id == "SV1":
            # SV1*HC:procedure_code*charges*UN*1***1
            if len(elements) > 1:
                proc = elements[1]
                if ":" in proc:
                    proc_code = proc.split(":")[1]
                else:
                    proc_code = proc
                if proc_code:
                    procedure_codes.append(proc_code)
            else:
                raw_errors.append("SV1 segment missing Procedure Code.")

        elif seg_id == "DMG":
            # DMG*D8*dob
            if len(elements) > 2 and elements[1] == "D8":
                patient_dob = elements[2]

        elif seg_id == "PRV":
            # PRV*PE*PXC*taxonomy_code
            if (
                len(elements) > 3
                and elements[1] == "PE"
                and elements[2] == "PXC"
            ):
                provider_taxonomy = elements[3]

    # Validate structural fields and log raw errors
    if not claim_id:
        raw_errors.append("Missing mandatory CLM segment or Claim ID.")
    if not patient_id:
        raw_errors.append(
            "Missing mandatory Patient identifier (NM1*QC Loop 2010BA)."
        )
    if not provider_npi:
        raw_errors.append(
            "Missing mandatory Provider NPI identifier (NM1*85 Loop 2010AA)."
        )
    if not service_date:
        raw_errors.append(
            "Missing mandatory Service Date (DTP segment with qualifier 472)."
        )
    if not diagnosis_codes:
        raw_errors.append(
            "Missing mandatory Diagnosis Codes. At least one HI segment is required."
        )
    if not procedure_codes:
        raw_errors.append(
            "Missing mandatory Procedure Codes. At least one SV1 segment is required."
        )

    parser_logger.info(
        f"Parsed EDI claim {claim_id} with {len(raw_errors)} raw structural errors."
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
        segments=segments_ir,
        raw_errors=raw_errors,
    )
