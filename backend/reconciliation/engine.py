"""
835-to-837 Reconciliation Engine — SQL-powered claim matching.

Matches 837 claims to 835 remittance payments using CLM01/CLP01 (ICN/DCN).
Leverages SQL JOINs across the persisted data.
"""
from __future__ import annotations

from typing import Any

import aiosqlite


async def reconcile(
    conn: aiosqlite.Connection,
    claim_interchange_id: int,
    remittance_interchange_id: int,
) -> dict[str, Any]:
    """
    Reconcile an 837 claims file against an 835 remittance file.

    Matches claims by patient_control_num (CLM01) to claim_id_ref (CLP01).

    Args:
        conn: Active SQLite connection.
        claim_interchange_id: Interchange ID of the 837 file.
        remittance_interchange_id: Interchange ID of the 835 file.

    Returns:
        Reconciliation report with matched, unmatched, and summary data.
    """
    # Matched claims via SQL JOIN
    matched_rows = await conn.execute_fetchall(
        """SELECT c.patient_control_num, c.total_charge AS billed,
                  rc.paid_amount AS paid, rc.claim_status,
                  rc.billed_amount AS remit_billed,
                  rc.patient_resp,
                  GROUP_CONCAT(DISTINCT a.reason_code) AS adjustment_codes,
                  GROUP_CONCAT(DISTINCT a.group_code) AS adjustment_groups,
                  COALESCE(SUM(a.amount), 0) AS total_adjustments
           FROM claims c
           LEFT JOIN remittance_claims rc
               ON rc.claim_id_ref = c.patient_control_num
               AND rc.interchange_id = ?
           LEFT JOIN adjustments a ON a.remittance_claim_id = rc.id
           WHERE c.interchange_id = ?
           GROUP BY c.id""",
        (remittance_interchange_id, claim_interchange_id),
    )

    matched: list[dict[str, Any]] = []
    unmatched_claims: list[dict[str, Any]] = []

    for row in matched_rows:
        r = dict(row)
        if r["paid"] is not None:
            # Determine status
            billed = float(r["billed"] or 0)
            paid = float(r["paid"] or 0)
            if paid == 0:
                status = "Denied"
            elif abs(paid - billed) < 0.01:
                status = "Paid in Full"
            else:
                status = "Partial"

            matched.append({
                "claim_id": r["patient_control_num"],
                "billed_amount": billed,
                "paid_amount": paid,
                "patient_responsibility": float(r["patient_resp"] or 0),
                "total_adjustments": float(r["total_adjustments"]),
                "adjustment_codes": r["adjustment_codes"] or "",
                "adjustment_groups": r["adjustment_groups"] or "",
                "claim_status": r["claim_status"],
                "status": status,
            })
        else:
            unmatched_claims.append({
                "claim_id": r["patient_control_num"],
                "billed_amount": float(r["billed"] or 0),
                "status": "Unmatched",
            })

    # Unmatched remittance claims (in 835 but not in 837)
    unmatched_remit_rows = await conn.execute_fetchall(
        """SELECT rc.claim_id_ref, rc.billed_amount, rc.paid_amount, rc.claim_status
           FROM remittance_claims rc
           WHERE rc.interchange_id = ?
             AND rc.claim_id_ref NOT IN (
                 SELECT c.patient_control_num FROM claims c
                 WHERE c.interchange_id = ?
             )""",
        (remittance_interchange_id, claim_interchange_id),
    )
    unmatched_remittances = [
        {
            "claim_id": dict(r)["claim_id_ref"],
            "billed_amount": float(dict(r)["billed_amount"] or 0),
            "paid_amount": float(dict(r)["paid_amount"] or 0),
            "status": "Unmatched (835 only)",
        }
        for r in unmatched_remit_rows
    ]

    # Summary
    total_billed = sum(m["billed_amount"] for m in matched)
    total_paid = sum(m["paid_amount"] for m in matched)
    total_adjustments = sum(m["total_adjustments"] for m in matched)

    return {
        "matched": matched,
        "unmatched_claims": unmatched_claims,
        "unmatched_remittances": unmatched_remittances,
        "summary": {
            "total_matched": len(matched),
            "total_unmatched_claims": len(unmatched_claims),
            "total_unmatched_remittances": len(unmatched_remittances),
            "total_billed": round(total_billed, 2),
            "total_paid": round(total_paid, 2),
            "total_adjustments": round(total_adjustments, 2),
            "net_difference": round(total_billed - total_paid - total_adjustments, 2),
        },
    }
