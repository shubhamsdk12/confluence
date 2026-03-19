"""
SNIP Level 1 — EDI Syntax Integrity.

Validates envelope structure:
  - ISA13 must match IEA02
  - GS06 must match GE02
  - ST02 must match SE02
  - SE01 must equal actual segment count between ST..SE (inclusive)

Reference: snip_validation_logic.md
"""
from __future__ import annotations

import aiosqlite

from parser.models import ValidationError, Severity


async def check_snip1(conn: aiosqlite.Connection, interchange_id: int) -> list[ValidationError]:
    """Run all SNIP Level 1 checks against the interchanges table."""
    errors: list[ValidationError] = []

    row = await conn.execute_fetchall(
        "SELECT * FROM interchanges WHERE id = ?", (interchange_id,)
    )
    if not row:
        errors.append(ValidationError(
            snip_level=1,
            severity=Severity.ERROR,
            code="SNIP1_NO_RECORD",
            message=f"No interchange record found for id={interchange_id}",
        ))
        return errors

    rec = dict(row[0])

    # --- ISA13 vs IEA02 ---
    isa = (rec.get("isa_control_num") or "").strip()
    iea = (rec.get("iea_control_num") or "").strip()
    if isa and iea and isa != iea:
        errors.append(ValidationError(
            segment_id="IEA",
            element_position=2,
            snip_level=1,
            severity=Severity.ERROR,
            code="SNIP1_ISA_IEA_MISMATCH",
            message=f"ISA13 control number '{isa}' does not match IEA02 '{iea}'",
            suggestion="Correct IEA02 to match ISA13, or verify the interchange was not truncated.",
        ))

    # --- GS06 vs GE02 ---
    gs = (rec.get("gs_control_num") or "").strip()
    ge = (rec.get("ge_control_num") or "").strip()
    if gs and ge and gs != ge:
        errors.append(ValidationError(
            segment_id="GE",
            element_position=2,
            snip_level=1,
            severity=Severity.ERROR,
            code="SNIP1_GS_GE_MISMATCH",
            message=f"GS06 control number '{gs}' does not match GE02 '{ge}'",
            suggestion="Correct GE02 to match GS06.",
        ))

    # --- ST02 vs SE02 ---
    st = (rec.get("st_control_num") or "").strip()
    se = (rec.get("se_control_num") or "").strip()
    if st and se and st != se:
        errors.append(ValidationError(
            segment_id="SE",
            element_position=2,
            snip_level=1,
            severity=Severity.ERROR,
            code="SNIP1_ST_SE_MISMATCH",
            message=f"ST02 control number '{st}' does not match SE02 '{se}'",
            suggestion="Correct SE02 to match ST02.",
        ))

    # --- SE01 segment count ---
    se_count = rec.get("se_segment_count")
    actual_count = rec.get("actual_segment_count")
    if se_count is not None and actual_count is not None and se_count != actual_count:
        errors.append(ValidationError(
            segment_id="SE",
            element_position=1,
            snip_level=1,
            severity=Severity.ERROR,
            code="SNIP1_SEGMENT_COUNT",
            message=f"SE01 declares {se_count} segments but actual count is {actual_count}",
            suggestion="Update SE01 to reflect the correct number of segments between ST and SE (inclusive).",
        ))

    return errors
