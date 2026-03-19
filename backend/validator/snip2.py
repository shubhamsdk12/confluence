"""
SNIP Level 2 — HIPAA Implementation Compliance.

Validates:
  - NPI format + Luhn check (delegated to npi.validate_npi)
  - Date format CCYYMMDD
  - Mandatory segments per transaction type
  - Postal code format (5 or 9 digits)

Reference: snip_validation_logic.md, npi_lookup_guide.md
"""
from __future__ import annotations

import re

import aiosqlite

from parser.models import ValidationError, Severity
from validator.npi import validate_npi_luhn


# ---------------------------------------------------------------------------
# Date validation
# ---------------------------------------------------------------------------
_DATE_RE = re.compile(r"^\d{8}$")  # CCYYMMDD

def _is_valid_date(d: str) -> bool:
    """Check if a string is in CCYYMMDD format with plausible values."""
    if not _DATE_RE.match(d):
        return False
    try:
        year, month, day = int(d[:4]), int(d[4:6]), int(d[6:8])
        return 1900 <= year <= 2099 and 1 <= month <= 12 and 1 <= day <= 31
    except (ValueError, IndexError):
        return False


# ---------------------------------------------------------------------------
# Postal code
# ---------------------------------------------------------------------------
_ZIP_RE = re.compile(r"^\d{5}(\d{4})?$")


# ---------------------------------------------------------------------------
# SNIP 2 checks
# ---------------------------------------------------------------------------

async def check_snip2(conn: aiosqlite.Connection, interchange_id: int) -> list[ValidationError]:
    """Run all SNIP Level 2 checks."""
    errors: list[ValidationError] = []

    # Determine transaction type
    rows = await conn.execute_fetchall(
        "SELECT transaction_type FROM interchanges WHERE id = ?", (interchange_id,)
    )
    if not rows:
        return errors
    tx_type = dict(rows[0])["transaction_type"]

    # ---- NPI Validation (837 only) ----
    if tx_type in ("837P", "837I"):
        claims = await conn.execute_fetchall(
            "SELECT id, billing_npi, rendering_npi, patient_control_num FROM claims WHERE interchange_id = ?",
            (interchange_id,),
        )
        for c in claims:
            claim = dict(c)
            for npi_field in ("billing_npi", "rendering_npi"):
                npi_val = (claim.get(npi_field) or "").strip()
                if not npi_val:
                    if npi_field == "billing_npi":
                        errors.append(ValidationError(
                            segment_id="NM1",
                            snip_level=2,
                            severity=Severity.ERROR,
                            code="SNIP2_MISSING_BILLING_NPI",
                            message=f"Claim '{claim.get('patient_control_num')}' is missing a billing NPI",
                            suggestion="Add NM109 with a valid 10-digit NPI in the 2010AA loop.",
                        ))
                    continue

                is_valid, detail = validate_npi_luhn(npi_val)
                if not is_valid:
                    errors.append(ValidationError(
                        segment_id="NM1",
                        element_position=9,
                        snip_level=2,
                        severity=Severity.ERROR,
                        code="SNIP2_INVALID_NPI",
                        message=f"NPI '{npi_val}' failed validation: {detail}",
                        suggestion="Verify the NPI in the NPPES registry and correct the value.",
                    ))

        # Mandatory segments check — must have at least one claim
        if not claims:
            errors.append(ValidationError(
                segment_id="CLM",
                snip_level=2,
                severity=Severity.ERROR,
                code="SNIP2_MISSING_CLM",
                message="837 transaction has no CLM (claim) segments",
                suggestion="A valid 837 must contain at least one CLM segment in loop 2300.",
            ))

    # ---- Date validation (all types) ----
    # Check service line dates for 837
    if tx_type in ("837P", "837I"):
        svc_lines = await conn.execute_fetchall(
            "SELECT id, date_of_service, procedure_code FROM service_lines WHERE interchange_id = ?",
            (interchange_id,),
        )
        for sl in svc_lines:
            sline = dict(sl)
            dos = (sline.get("date_of_service") or "").strip()
            if dos and not _is_valid_date(dos):
                errors.append(ValidationError(
                    segment_id="DTP",
                    element_position=3,
                    snip_level=2,
                    severity=Severity.ERROR,
                    code="SNIP2_INVALID_DATE",
                    message=f"Date of service '{dos}' does not conform to CCYYMMDD format",
                    suggestion="Correct DTP03 to use the CCYYMMDD date format (e.g., 20230915).",
                ))

    # Check member dates for 834
    if tx_type == "834":
        members = await conn.execute_fetchall(
            "SELECT id, subscriber_id, benefit_start, benefit_end FROM members WHERE interchange_id = ?",
            (interchange_id,),
        )
        if not members:
            errors.append(ValidationError(
                segment_id="INS",
                snip_level=2,
                severity=Severity.ERROR,
                code="SNIP2_MISSING_INS",
                message="834 transaction has no INS (member) segments",
                suggestion="A valid 834 must contain at least one INS segment in loop 2000.",
            ))

        for m in members:
            member = dict(m)
            for date_field in ("benefit_start", "benefit_end"):
                date_val = (member.get(date_field) or "").strip()
                if date_val and not _is_valid_date(date_val):
                    errors.append(ValidationError(
                        segment_id="DTP",
                        element_position=3,
                        snip_level=2,
                        severity=Severity.ERROR,
                        code="SNIP2_INVALID_DATE",
                        message=f"Member '{member.get('subscriber_id')}' has invalid {date_field}: '{date_val}'",
                        suggestion="Correct DTP03 to use the CCYYMMDD date format.",
                    ))

    # 835 mandatory checks
    if tx_type == "835":
        payments = await conn.execute_fetchall(
            "SELECT id FROM payments WHERE interchange_id = ?", (interchange_id,)
        )
        if not payments:
            errors.append(ValidationError(
                segment_id="BPR",
                snip_level=2,
                severity=Severity.ERROR,
                code="SNIP2_MISSING_BPR",
                message="835 transaction has no BPR (payment) segment",
                suggestion="A valid 835 must contain a BPR segment in the header.",
            ))

        rem_claims = await conn.execute_fetchall(
            "SELECT id FROM remittance_claims WHERE interchange_id = ?", (interchange_id,)
        )
        if not rem_claims:
            errors.append(ValidationError(
                segment_id="CLP",
                snip_level=2,
                severity=Severity.ERROR,
                code="SNIP2_MISSING_CLP",
                message="835 transaction has no CLP (remittance claim) segments",
                suggestion="A valid 835 must contain at least one CLP segment in loop 2100.",
            ))

    return errors
