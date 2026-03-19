"""
Validation Engine — orchestrates SNIP Level 1, 2, and 3 checks.

Runs all validators against persisted data in SQLite and collects
ValidationError results. Also persists errors to the DB.
"""
from __future__ import annotations

import aiosqlite

from parser.models import ValidationError
from database.repository import save_validation_errors
from validator.snip1 import check_snip1
from validator.snip2 import check_snip2
from validator.snip3 import check_snip3


async def validate(conn: aiosqlite.Connection, interchange_id: int) -> list[ValidationError]:
    """
    Run all SNIP 1-3 validation checks against a persisted interchange.

    Args:
        conn: Active SQLite connection.
        interchange_id: The interchange to validate.

    Returns:
        Combined list of ValidationError objects from all SNIP levels.
    """
    all_errors: list[ValidationError] = []

    # SNIP Level 1 — Envelope Integrity
    snip1_errors = await check_snip1(conn, interchange_id)
    all_errors.extend(snip1_errors)

    # SNIP Level 2 — HIPAA Implementation Compliance
    snip2_errors = await check_snip2(conn, interchange_id)
    all_errors.extend(snip2_errors)

    # SNIP Level 3 — Cross-Segment Balancing
    snip3_errors = await check_snip3(conn, interchange_id)
    all_errors.extend(snip3_errors)

    # Persist all errors to the DB
    if all_errors:
        await save_validation_errors(conn, interchange_id, all_errors)

    return all_errors
