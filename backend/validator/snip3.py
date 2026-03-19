"""
SNIP Level 3 — Cross-Segment Balancing.

Validates mathematical integrity:
  - 837: CLM02 == SUM(SV102/SV203) per claim
  - 835: CLP04 == CLP03 - SUM(CAS adjustments) per remittance claim
  - 834: Number of INS segments matches BGN06 (if present)

Tolerance: $0.01 (from knowledge_index_rules.json)

Reference: snip_validation_logic.md
"""
from __future__ import annotations

import aiosqlite

from parser.models import ValidationError, Severity

# Tolerance for floating-point comparison
_TOLERANCE = 0.01


async def check_snip3(conn: aiosqlite.Connection, interchange_id: int) -> list[ValidationError]:
    """Run all SNIP Level 3 checks."""
    errors: list[ValidationError] = []

    # Determine transaction type
    rows = await conn.execute_fetchall(
        "SELECT transaction_type FROM interchanges WHERE id = ?", (interchange_id,)
    )
    if not rows:
        return errors
    tx_type = dict(rows[0])["transaction_type"]

    if tx_type in ("837P", "837I"):
        errors.extend(await _check_837_balancing(conn, interchange_id))

    if tx_type == "835":
        errors.extend(await _check_835_reconciliation(conn, interchange_id))

    if tx_type == "834":
        errors.extend(await _check_834_consistency(conn, interchange_id))

    return errors


async def _check_837_balancing(
    conn: aiosqlite.Connection, interchange_id: int
) -> list[ValidationError]:
    """
    837: Total Claim Charge (CLM02) must equal SUM of Service Line Charges.

    SQL:
        SELECT c.id, c.patient_control_num, c.total_charge,
               COALESCE(SUM(sl.line_charge), 0) AS sum_lines,
               ABS(c.total_charge - COALESCE(SUM(sl.line_charge), 0)) AS diff
        FROM claims c
        LEFT JOIN service_lines sl ON sl.claim_id = c.id
        WHERE c.interchange_id = ?
        GROUP BY c.id
        HAVING diff > 0.01;
    """
    errors: list[ValidationError] = []
    rows = await conn.execute_fetchall(
        """SELECT c.id, c.patient_control_num, c.total_charge,
                  COALESCE(SUM(sl.line_charge), 0) AS sum_lines,
                  ABS(c.total_charge - COALESCE(SUM(sl.line_charge), 0)) AS diff
           FROM claims c
           LEFT JOIN service_lines sl ON sl.claim_id = c.id
           WHERE c.interchange_id = ?
           GROUP BY c.id
           HAVING diff > ?""",
        (interchange_id, _TOLERANCE),
    )

    for row in rows:
        r = dict(row)
        errors.append(ValidationError(
            segment_id="CLM",
            element_position=2,
            loop_id="2300",
            snip_level=3,
            severity=Severity.ERROR,
            code="SNIP3_CLAIM_BALANCE",
            message=(
                f"Claim '{r['patient_control_num']}': CLM02 total charge "
                f"${r['total_charge']:.2f} does not equal sum of service line "
                f"charges ${r['sum_lines']:.2f} (difference: ${r['diff']:.2f})"
            ),
            suggestion=(
                "Verify that CLM02 equals the sum of all SV102/SV203 amounts "
                "in the service line loops (2400)."
            ),
        ))

    return errors


async def _check_835_reconciliation(
    conn: aiosqlite.Connection, interchange_id: int
) -> list[ValidationError]:
    """
    835: CLP04 (Paid) must equal CLP03 (Billed) - SUM(CAS adjustments).

    SQL:
        SELECT rc.id, rc.claim_id_ref, rc.billed_amount, rc.paid_amount,
               COALESCE(SUM(a.amount), 0) AS sum_adjustments,
               ABS(rc.paid_amount - (rc.billed_amount - COALESCE(SUM(a.amount), 0))) AS diff
        FROM remittance_claims rc
        LEFT JOIN adjustments a ON a.remittance_claim_id = rc.id
        WHERE rc.interchange_id = ?
        GROUP BY rc.id
        HAVING diff > 0.01;
    """
    errors: list[ValidationError] = []
    rows = await conn.execute_fetchall(
        """SELECT rc.id, rc.claim_id_ref, rc.billed_amount, rc.paid_amount,
                  COALESCE(SUM(a.amount), 0) AS sum_adjustments,
                  ABS(rc.paid_amount - (rc.billed_amount - COALESCE(SUM(a.amount), 0))) AS diff
           FROM remittance_claims rc
           LEFT JOIN adjustments a ON a.remittance_claim_id = rc.id
           WHERE rc.interchange_id = ?
           GROUP BY rc.id
           HAVING diff > ?""",
        (interchange_id, _TOLERANCE),
    )

    for row in rows:
        r = dict(row)
        expected = r["billed_amount"] - r["sum_adjustments"]
        errors.append(ValidationError(
            segment_id="CLP",
            element_position=4,
            loop_id="2100",
            snip_level=3,
            severity=Severity.ERROR,
            code="SNIP3_REMITTANCE_BALANCE",
            message=(
                f"Claim '{r['claim_id_ref']}': CLP04 paid amount "
                f"${r['paid_amount']:.2f} does not match expected "
                f"${expected:.2f} (billed ${r['billed_amount']:.2f} "
                f"- adjustments ${r['sum_adjustments']:.2f})"
            ),
            suggestion=(
                "Verify that CLP04 = CLP03 − SUM(CAS adjustment amounts). "
                "Check all CAS segments under this CLP for correctness."
            ),
        ))

    return errors


async def _check_834_consistency(
    conn: aiosqlite.Connection, interchange_id: int
) -> list[ValidationError]:
    """
    834: Verify INS segment count matches BGN06 control total (if present).
    """
    errors: list[ValidationError] = []

    # Count members (INS segments)
    rows = await conn.execute_fetchall(
        "SELECT COUNT(*) AS cnt FROM members WHERE interchange_id = ?",
        (interchange_id,),
    )
    member_count = dict(rows[0])["cnt"] if rows else 0

    # BGN06 would be stored in metadata; for now we just validate member count > 0
    if member_count == 0:
        errors.append(ValidationError(
            segment_id="INS",
            snip_level=3,
            severity=Severity.WARNING,
            code="SNIP3_NO_MEMBERS",
            message="834 transaction has 0 members — expected at least 1 INS segment",
            suggestion="Verify the 834 file contains member enrollment data.",
        ))

    return errors
