"""
Transaction type auto-detection from ISA/GS/ST envelope segments.

Per architecture.md §1 — Identification Service:
  - GS01 (Functional Group Code) + ST01 (Transaction Set ID)
  - 837 + HC → 837P  |  837 + HI → 837I  |  835 → Remittance  |  834 → Enrollment
"""
from parser.models import Delimiters, EnvelopeInfo, TransactionType


class IdentificationError(Exception):
    """Raised when envelope segments cannot be identified."""


def identify_transaction(raw: str, delimiters: Delimiters) -> tuple[TransactionType, EnvelopeInfo]:
    """
    Scan ISA, GS, and ST segments to determine the transaction type and
    extract envelope metadata.

    Args:
        raw: Full raw EDI content.
        delimiters: Previously extracted delimiters.

    Returns:
        A tuple of (TransactionType, EnvelopeInfo).
    """
    seg_term = delimiters.segment_terminator
    elem_sep = delimiters.element_separator

    # Split into raw segments and strip whitespace
    raw_segments = [s.strip() for s in raw.split(seg_term) if s.strip()]

    envelope = EnvelopeInfo()
    gs_code = ""
    st_code = ""

    for seg_raw in raw_segments:
        elements = seg_raw.split(elem_sep)
        seg_id = elements[0].upper().strip()

        if seg_id == "ISA" and len(elements) >= 14:
            envelope.sender_id = elements[6].strip()
            envelope.receiver_id = elements[8].strip()
            envelope.interchange_control_number = elements[13].strip()
            if len(elements) >= 10:
                envelope.isa_date = elements[9].strip()
            if len(elements) >= 11:
                envelope.isa_time = elements[10].strip()

        elif seg_id == "GS" and len(elements) >= 7:
            gs_code = elements[1].strip().upper()
            envelope.gs_code = gs_code
            envelope.functional_group_control_number = elements[6].strip()

        elif seg_id == "ST" and len(elements) >= 3:
            st_code = elements[1].strip()
            envelope.st_code = st_code
            envelope.transaction_set_control_number = elements[2].strip()
            break  # We have all we need

    tx_type = _resolve_type(gs_code, st_code)
    return tx_type, envelope


def _resolve_type(gs_code: str, st_code: str) -> TransactionType:
    """
    Map GS01 + ST01 to a TransactionType enum.

    Mapping rules:
      ST01=837  +  GS01=HC  → 837P (Professional)
      ST01=837  +  GS01=HI  → 837I (Institutional)   — NOTE: GS01 'HI' is rare;
                                some institutional files also use 'HC'. We fall
                                back to 837P when GS01 is ambiguous.
      ST01=835              → Remittance
      ST01=834              → Enrollment
    """
    if st_code == "835":
        return TransactionType.REMITTANCE_835
    if st_code == "834":
        return TransactionType.ENROLLMENT_834
    if st_code == "837":
        if gs_code == "HI":
            return TransactionType.CLAIM_837I
        # HC (Professional) or any other GS code defaults to 837P
        return TransactionType.CLAIM_837P
    return TransactionType.UNKNOWN
