"""
Repository — maps the parsed Loop/Segment tree into relational tables.

Walks the hierarchical ParseResult and inserts rows into the appropriate
SQLite tables based on transaction type (837, 835, 834).
"""
from __future__ import annotations

import json
from typing import Any

import aiosqlite

from parser.models import Loop, ParseResult, Segment, TransactionType, ValidationError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _el(segment: Segment, position: int, default: str = "") -> str:
    """Safely get element value at a given position (0-based)."""
    if position < len(segment.elements):
        return segment.elements[position].value.strip()
    return default


def _el_float(segment: Segment, position: int, default: float = 0.0) -> float:
    """Safely get a float element value."""
    val = _el(segment, position)
    try:
        return float(val) if val else default
    except (ValueError, TypeError):
        return default


def _collect_segments(loops: list[Loop]) -> list[tuple[str, Segment]]:
    """
    Recursively flatten all segments from the loop tree,
    returning tuples of (loop_id, segment).
    """
    result: list[tuple[str, Segment]] = []
    for loop in loops:
        for seg in loop.segments:
            result.append((loop.loop_id, seg))
        if loop.children:
            result.extend(_collect_segments(loop.children))
    return result


def _find_segments(flat: list[tuple[str, Segment]], seg_id: str) -> list[tuple[str, Segment]]:
    """Filter flattened segments by segment ID."""
    return [(lid, s) for lid, s in flat if s.segment_id.upper() == seg_id.upper()]


# ---------------------------------------------------------------------------
# Envelope persistence
# ---------------------------------------------------------------------------

async def _persist_interchange(
    conn: aiosqlite.Connection,
    file_name: str,
    result: ParseResult,
    flat: list[tuple[str, Segment]],
) -> int:
    """Insert the interchange envelope record and return its ID."""
    # Grab IEA, GE, SE values from parsed segments
    iea_control = ""
    ge_control = ""
    se_control = ""
    se_seg_count = 0

    for _, seg in flat:
        sid = seg.segment_id.upper()
        if sid == "IEA":
            iea_control = _el(seg, 2)
        elif sid == "GE":
            ge_control = _el(seg, 2)
        elif sid == "SE":
            se_seg_count_str = _el(seg, 1)
            se_control = _el(seg, 2)
            try:
                se_seg_count = int(se_seg_count_str) if se_seg_count_str else 0
            except ValueError:
                se_seg_count = 0

    # Count segments between ST and SE (inclusive) for SNIP-1 verification
    actual_count = 0
    counting = False
    for _, seg in flat:
        sid = seg.segment_id.upper()
        if sid == "ST":
            counting = True
        if counting:
            actual_count += 1
        if sid == "SE":
            counting = False

    cursor = await conn.execute(
        """INSERT INTO interchanges
           (file_name, transaction_type, isa_control_num, iea_control_num,
            sender_id, receiver_id, gs_control_num, ge_control_num,
            st_control_num, se_control_num, se_segment_count, actual_segment_count)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            file_name,
            result.transaction_type.value,
            result.envelope.interchange_control_number,
            iea_control,
            result.envelope.sender_id,
            result.envelope.receiver_id,
            result.envelope.functional_group_control_number,
            ge_control,
            result.envelope.transaction_set_control_number,
            se_control,
            se_seg_count,
            actual_count,
        ),
    )
    await conn.commit()
    return cursor.lastrowid  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# 837 Persistence
# ---------------------------------------------------------------------------

async def _persist_837(
    conn: aiosqlite.Connection,
    interchange_id: int,
    flat: list[tuple[str, Segment]],
) -> None:
    """Extract and persist 837 claims and service lines."""
    # Walk segments in order, building claims
    current_claim_id: int | None = None
    billing_npi: str = ""
    rendering_npi: str = ""
    subscriber_id: str = ""
    diagnosis_codes: list[str] = []

    for loop_id, seg in flat:
        sid = seg.segment_id.upper()

        # Billing Provider NPI (NM1*85)
        if sid == "NM1" and _el(seg, 1) == "85":
            billing_npi = _el(seg, 9)

        # Rendering Provider NPI (NM1*82)
        if sid == "NM1" and _el(seg, 1) == "82":
            rendering_npi = _el(seg, 9)

        # Subscriber (NM1*IL)
        if sid == "NM1" and _el(seg, 1) == "IL":
            subscriber_id = _el(seg, 9)

        # Diagnosis codes from HI
        if sid == "HI":
            for i in range(1, len(seg.elements)):
                val = _el(seg, i)
                if ":" in val:
                    code = val.split(":")[1] if len(val.split(":")) > 1 else val
                    if code:
                        diagnosis_codes.append(code)

        # Claim (CLM)
        if sid == "CLM":
            cursor = await conn.execute(
                """INSERT INTO claims
                   (interchange_id, patient_control_num, total_charge,
                    place_of_service, diagnosis_codes, billing_npi,
                    rendering_npi, subscriber_id, loop_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    interchange_id,
                    _el(seg, 1),                    # CLM01
                    _el_float(seg, 2),               # CLM02
                    _el(seg, 5),                     # CLM05
                    json.dumps(diagnosis_codes),
                    billing_npi,
                    rendering_npi,
                    subscriber_id,
                    loop_id,
                ),
            )
            current_claim_id = cursor.lastrowid
            diagnosis_codes = []  # Reset for next claim

        # Service Line (SV1 for professional, SV2 for institutional)
        if sid in ("SV1", "SV2") and current_claim_id is not None:
            if sid == "SV1":
                proc_raw = _el(seg, 1)
                proc_code = proc_raw.split(":")[1] if ":" in proc_raw else proc_raw
                line_charge = _el_float(seg, 2)
                units = _el_float(seg, 4)
            else:  # SV2
                proc_raw = _el(seg, 2)
                proc_code = proc_raw.split(":")[1] if ":" in proc_raw else proc_raw
                line_charge = _el_float(seg, 3)
                units = _el_float(seg, 5)

            await conn.execute(
                """INSERT INTO service_lines
                   (claim_id, interchange_id, procedure_code, line_charge,
                    units, date_of_service, loop_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    current_claim_id,
                    interchange_id,
                    proc_code,
                    line_charge,
                    units,
                    "",  # DTP filled below
                    loop_id,
                ),
            )

    await conn.commit()


# ---------------------------------------------------------------------------
# 835 Persistence
# ---------------------------------------------------------------------------

async def _persist_835(
    conn: aiosqlite.Connection,
    interchange_id: int,
    flat: list[tuple[str, Segment]],
) -> None:
    """Extract and persist 835 payment/remittance data."""
    payment_id: int | None = None
    current_rc_id: int | None = None
    # Track context: only claim-level CAS segments count for SNIP-3 balancing.
    # Service-line CAS (under SVC) are a different scope.
    cas_context: str = "none"  # "claim" or "service"

    for loop_id, seg in flat:
        sid = seg.segment_id.upper()

        # Financial header (BPR)
        if sid == "BPR":
            total_payment = _el_float(seg, 2)
            payment_method = _el(seg, 4)
            check_date = _el(seg, 16)
            cursor = await conn.execute(
                """INSERT INTO payments
                   (interchange_id, total_payment, payment_method, check_date)
                   VALUES (?, ?, ?, ?)""",
                (interchange_id, total_payment, payment_method, check_date),
            )
            payment_id = cursor.lastrowid

        # Trace number (TRN)
        if sid == "TRN" and payment_id is not None:
            await conn.execute(
                "UPDATE payments SET trace_number = ? WHERE id = ?",
                (_el(seg, 2), payment_id),
            )

        # Remittance claim (CLP) → switch context to "claim"
        if sid == "CLP" and payment_id is not None:
            cursor = await conn.execute(
                """INSERT INTO remittance_claims
                   (payment_id, interchange_id, claim_id_ref, claim_status,
                    billed_amount, paid_amount, patient_resp, loop_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    payment_id,
                    interchange_id,
                    _el(seg, 1),          # CLP01 — claim ID / DCN
                    _el(seg, 2),          # CLP02 — status
                    _el_float(seg, 3),     # CLP03 — billed
                    _el_float(seg, 4),     # CLP04 — paid
                    _el_float(seg, 5),     # CLP05 — patient responsibility
                    loop_id,
                ),
            )
            current_rc_id = cursor.lastrowid
            cas_context = "claim"

        # SVC segment → switch context to "service"
        if sid == "SVC":
            cas_context = "service"

        # Adjustments (CAS) — only persist claim-level CAS for SNIP-3 balancing
        if sid == "CAS" and current_rc_id is not None and cas_context == "claim":
            # CAS segments can carry up to 6 adjustment triplets:
            # CAS01=group, CAS02=reason1, CAS03=amount1, CAS05=reason2, CAS06=amount2, ...
            group_code = _el(seg, 1)
            i = 2
            while i < len(seg.elements):
                reason = _el(seg, i)
                amount = _el_float(seg, i + 1) if (i + 1) < len(seg.elements) else 0.0
                if reason:
                    await conn.execute(
                        """INSERT INTO adjustments
                           (remittance_claim_id, group_code, reason_code, amount)
                           VALUES (?, ?, ?, ?)""",
                        (current_rc_id, group_code, reason, amount),
                    )
                i += 3  # Move to next triplet

    await conn.commit()


# ---------------------------------------------------------------------------
# 834 Persistence
# ---------------------------------------------------------------------------

async def _persist_834(
    conn: aiosqlite.Connection,
    interchange_id: int,
    flat: list[tuple[str, Segment]],
) -> None:
    """Extract and persist 834 enrollment/member data."""
    # We accumulate member fields as we encounter segments
    member_data: dict[str, Any] = {}
    members_to_insert: list[dict[str, Any]] = []

    def _flush_member():
        if member_data.get("_has_ins"):
            members_to_insert.append(dict(member_data))

    for loop_id, seg in flat:
        sid = seg.segment_id.upper()

        # New member (INS starts a new member block)
        if sid == "INS":
            _flush_member()
            member_data = {
                "_has_ins": True,
                "member_indicator": _el(seg, 1),   # Y=Subscriber
                "maintenance_code": _el(seg, 3),    # 021=Add, 024=Term
            }

        # Subscriber ID (REF*0F)
        if sid == "REF" and _el(seg, 1) == "0F":
            member_data["subscriber_id"] = _el(seg, 2)

        # Member name (NM1*IL)
        if sid == "NM1" and _el(seg, 1) == "IL":
            member_data["last_name"] = _el(seg, 3)
            member_data["first_name"] = _el(seg, 4)
            member_data["ssn"] = _el(seg, 9)

        # Coverage (HD)
        if sid == "HD":
            member_data["insurance_type"] = _el(seg, 4)

        # Benefit dates (DTP*348 = start, DTP*349 = end)
        if sid == "DTP":
            qualifier = _el(seg, 1)
            date_val = _el(seg, 3)
            if qualifier == "348":
                member_data["benefit_start"] = date_val
            elif qualifier == "349":
                member_data["benefit_end"] = date_val

    # Flush last member
    _flush_member()

    # Bulk insert
    for m in members_to_insert:
        await conn.execute(
            """INSERT INTO members
               (interchange_id, subscriber_id, ssn, last_name, first_name,
                maintenance_code, member_indicator, insurance_type,
                benefit_start, benefit_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                interchange_id,
                m.get("subscriber_id", ""),
                m.get("ssn", ""),
                m.get("last_name", ""),
                m.get("first_name", ""),
                m.get("maintenance_code", ""),
                m.get("member_indicator", ""),
                m.get("insurance_type", ""),
                m.get("benefit_start", ""),
                m.get("benefit_end", ""),
            ),
        )
    await conn.commit()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def persist_parse_result(
    conn: aiosqlite.Connection,
    file_name: str,
    result: ParseResult,
) -> int:
    """
    Persist a ParseResult into the relational database.

    Walks the loop tree, flattens all segments, and dispatches to
    transaction-type-specific persistence handlers.

    Returns:
        The interchange_id of the persisted record.
    """
    flat = _collect_segments(result.loops)

    interchange_id = await _persist_interchange(conn, file_name, result, flat)

    tx = result.transaction_type
    if tx in (TransactionType.CLAIM_837P, TransactionType.CLAIM_837I):
        await _persist_837(conn, interchange_id, flat)
    elif tx == TransactionType.REMITTANCE_835:
        await _persist_835(conn, interchange_id, flat)
    elif tx == TransactionType.ENROLLMENT_834:
        await _persist_834(conn, interchange_id, flat)

    return interchange_id


async def get_interchange(conn: aiosqlite.Connection, interchange_id: int) -> dict[str, Any]:
    """Fetch a single interchange with summary info."""
    row = await conn.execute_fetchall(
        "SELECT * FROM interchanges WHERE id = ?", (interchange_id,)
    )
    if not row:
        return {}
    return dict(row[0])


async def save_validation_errors(
    conn: aiosqlite.Connection,
    interchange_id: int,
    errors: list[ValidationError],
) -> None:
    """Bulk insert validation errors for an interchange."""
    for err in errors:
        await conn.execute(
            """INSERT INTO validation_errors
               (interchange_id, segment_id, element_position, loop_id,
                snip_level, severity, code, message, suggestion)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                interchange_id,
                err.segment_id,
                err.element_position,
                err.loop_id,
                err.snip_level,
                err.severity.value,
                err.code,
                err.message,
                err.suggestion,
            ),
        )
    await conn.commit()
