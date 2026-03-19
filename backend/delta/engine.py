"""
834 Delta Engine — SQL-powered member enrollment diff.

Compares two 834 files (e.g., January vs February roster) to identify
net changes: added, terminated, changed, and unchanged members.
"""
from __future__ import annotations

from typing import Any

import aiosqlite


async def compute_delta(
    conn: aiosqlite.Connection,
    old_interchange_id: int,
    new_interchange_id: int,
) -> dict[str, Any]:
    """
    Compare two 834 enrollment files and return a delta report.

    Args:
        conn: Active SQLite connection.
        old_interchange_id: Interchange ID of the older 834 file.
        new_interchange_id: Interchange ID of the newer 834 file.

    Returns:
        Delta report with added, terminated, changed, unchanged members.
    """
    # Members added (in new but not in old)
    added_rows = await conn.execute_fetchall(
        """SELECT n.subscriber_id, n.last_name, n.first_name,
                  n.maintenance_code, n.insurance_type,
                  n.benefit_start, n.benefit_end
           FROM members n
           LEFT JOIN members o
               ON o.subscriber_id = n.subscriber_id
               AND o.interchange_id = ?
           WHERE n.interchange_id = ? AND o.id IS NULL""",
        (old_interchange_id, new_interchange_id),
    )
    added = [_member_dict(r, "Added") for r in added_rows]

    # Members terminated (in old but not in new)
    terminated_rows = await conn.execute_fetchall(
        """SELECT o.subscriber_id, o.last_name, o.first_name,
                  o.maintenance_code, o.insurance_type,
                  o.benefit_start, o.benefit_end
           FROM members o
           LEFT JOIN members n
               ON n.subscriber_id = o.subscriber_id
               AND n.interchange_id = ?
           WHERE o.interchange_id = ? AND n.id IS NULL""",
        (new_interchange_id, old_interchange_id),
    )
    terminated = [_member_dict(r, "Terminated") for r in terminated_rows]

    # Members in both files (potentially changed)
    both_rows = await conn.execute_fetchall(
        """SELECT o.subscriber_id,
                  o.last_name AS old_last, o.first_name AS old_first,
                  o.maintenance_code AS old_maint, o.insurance_type AS old_ins,
                  o.benefit_start AS old_start, o.benefit_end AS old_end,
                  n.last_name AS new_last, n.first_name AS new_first,
                  n.maintenance_code AS new_maint, n.insurance_type AS new_ins,
                  n.benefit_start AS new_start, n.benefit_end AS new_end
           FROM members o
           JOIN members n
               ON n.subscriber_id = o.subscriber_id
               AND n.interchange_id = ?
           WHERE o.interchange_id = ?""",
        (new_interchange_id, old_interchange_id),
    )

    changed: list[dict[str, Any]] = []
    unchanged_count = 0

    for row in both_rows:
        r = dict(row)
        diffs = _compute_field_diffs(r)
        if diffs:
            changed.append({
                "subscriber_id": r["subscriber_id"],
                "name": f"{r['new_last']}, {r['new_first']}",
                "status": "Changed",
                "changes": diffs,
            })
        else:
            unchanged_count += 1

    return {
        "added": added,
        "terminated": terminated,
        "changed": changed,
        "unchanged_count": unchanged_count,
        "summary": {
            "total_added": len(added),
            "total_terminated": len(terminated),
            "total_changed": len(changed),
            "total_unchanged": unchanged_count,
        },
    }


def _member_dict(row: Any, status: str) -> dict[str, Any]:
    """Convert a DB row to a member dict."""
    r = dict(row)
    return {
        "subscriber_id": r["subscriber_id"],
        "name": f"{r['last_name']}, {r['first_name']}",
        "maintenance_code": r["maintenance_code"],
        "insurance_type": r["insurance_type"],
        "benefit_start": r["benefit_start"],
        "benefit_end": r["benefit_end"],
        "status": status,
    }


def _compute_field_diffs(r: dict[str, Any]) -> list[dict[str, str]]:
    """Compare old vs new fields and return list of differences."""
    fields = [
        ("last_name", "old_last", "new_last"),
        ("first_name", "old_first", "new_first"),
        ("maintenance_code", "old_maint", "new_maint"),
        ("insurance_type", "old_ins", "new_ins"),
        ("benefit_start", "old_start", "new_start"),
        ("benefit_end", "old_end", "new_end"),
    ]
    diffs: list[dict[str, str]] = []
    for field_name, old_key, new_key in fields:
        old_val = (r.get(old_key) or "").strip()
        new_val = (r.get(new_key) or "").strip()
        if old_val != new_val:
            diffs.append({
                "field": field_name,
                "old_value": old_val,
                "new_value": new_val,
            })
    return diffs
