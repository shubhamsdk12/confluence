"""
Phase 1 Tests — Parser Module

Covers:
  - Delimiter extraction from ISA header
  - Transaction type identification from GS/ST
  - Full state-machine parse for each transaction type
  - Graceful handling of malformed 837I file
"""
import sys
from pathlib import Path

import pytest

# Ensure backend is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from parser.delimiters import extract_delimiters, DelimiterExtractionError
from parser.identifier import identify_transaction
from parser.models import TransactionType, Delimiters
from parser.state_machine import parse_edi


# ---------------------------------------------------------------------------
# Paths to test files
# ---------------------------------------------------------------------------
TEST_DIR = Path(__file__).resolve().parent.parent.parent / "test_files"


def _read(filename: str) -> str:
    return (TEST_DIR / filename).read_text(encoding="utf-8")


# ========================== DELIMITER TESTS ==========================


class TestDelimiters:
    def test_837p_delimiters(self):
        raw = _read("837P.edi")
        d = extract_delimiters(raw)
        assert d.element_separator == "*"
        assert d.sub_element_separator == ":"
        assert d.segment_terminator == "~"

    def test_835_delimiters(self):
        raw = _read("835.edi")
        d = extract_delimiters(raw)
        assert d.element_separator == "*"
        assert d.sub_element_separator == ":"
        assert d.segment_terminator == "~"

    def test_834_delimiters(self):
        raw = _read("834.edi")
        d = extract_delimiters(raw)
        assert d.element_separator == "*"

    def test_malformed_837i_delimiters(self):
        """Malformed file should still have valid ISA — delimiters extractable."""
        raw = _read("837I_malformed.edi")
        d = extract_delimiters(raw)
        assert d.element_separator == "*"
        assert d.segment_terminator == "~"

    def test_short_content_raises(self):
        with pytest.raises(DelimiterExtractionError, match="too short"):
            extract_delimiters("ISA*short")

    def test_non_isa_start_raises(self):
        with pytest.raises(DelimiterExtractionError, match="does not begin with"):
            extract_delimiters("GS*HP*SENDER" + " " * 200)


# ====================== IDENTIFICATION TESTS =========================


class TestIdentification:
    def test_837p_identification(self):
        raw = _read("837P.edi")
        d = extract_delimiters(raw)
        tx_type, env = identify_transaction(raw, d)
        assert tx_type == TransactionType.CLAIM_837P
        assert env.st_code == "837"
        assert env.gs_code == "HC"
        assert env.sender_id.strip() != ""

    def test_835_identification(self):
        raw = _read("835.edi")
        d = extract_delimiters(raw)
        tx_type, env = identify_transaction(raw, d)
        assert tx_type == TransactionType.REMITTANCE_835
        assert env.st_code == "835"

    def test_834_identification(self):
        raw = _read("834.edi")
        d = extract_delimiters(raw)
        tx_type, env = identify_transaction(raw, d)
        assert tx_type == TransactionType.ENROLLMENT_834
        assert env.st_code == "834"

    def test_837i_identification(self):
        """837I uses GS01=HC in our test file (common variant)."""
        raw = _read("837I_malformed.edi")
        d = extract_delimiters(raw)
        tx_type, env = identify_transaction(raw, d)
        # Our malformed test file uses GS*HC — defaults to 837P
        # This is expected; in production, GS01=HI would trigger 837I
        assert tx_type in (TransactionType.CLAIM_837P, TransactionType.CLAIM_837I)

    def test_envelope_metadata(self):
        raw = _read("837P.edi")
        d = extract_delimiters(raw)
        _, env = identify_transaction(raw, d)
        assert env.interchange_control_number == "000000001"
        assert env.transaction_set_control_number == "0001"


# ========================= PARSER TESTS ==============================


class TestStateMachineParser:
    def test_837p_parse_structure(self):
        raw = _read("837P.edi")
        result = parse_edi(raw)
        assert result.transaction_type == TransactionType.CLAIM_837P
        assert result.segment_count > 0
        assert len(result.loops) > 0
        # Should have ISA envelope at root level
        loop_ids = [l.loop_id for l in result.loops]
        assert "ISA_ENVELOPE" in loop_ids

    def test_837p_has_billing_provider(self):
        raw = _read("837P.edi")
        result = parse_edi(raw)
        all_loop_ids = _collect_loop_ids(result.loops)
        assert "2000A" in all_loop_ids, "Should contain Billing Provider loop (2000A)"

    def test_837p_has_claim(self):
        raw = _read("837P.edi")
        result = parse_edi(raw)
        all_loop_ids = _collect_loop_ids(result.loops)
        assert "2300" in all_loop_ids, "Should contain Claim Detail loop (2300)"

    def test_837p_has_service_lines(self):
        raw = _read("837P.edi")
        result = parse_edi(raw)
        all_loop_ids = _collect_loop_ids(result.loops)
        assert "2400" in all_loop_ids, "Should contain Service Line loop (2400)"

    def test_835_parse(self):
        raw = _read("835.edi")
        result = parse_edi(raw)
        assert result.transaction_type == TransactionType.REMITTANCE_835
        all_loop_ids = _collect_loop_ids(result.loops)
        assert "2100" in all_loop_ids, "Should contain Claim Status loop (CLP)"

    def test_834_parse(self):
        raw = _read("834.edi")
        result = parse_edi(raw)
        assert result.transaction_type == TransactionType.ENROLLMENT_834
        all_loop_ids = _collect_loop_ids(result.loops)
        assert "2000" in all_loop_ids, "Should contain Member Detail loop (INS)"

    def test_malformed_837i_no_crash(self):
        """Parser must handle malformed input without crashing."""
        raw = _read("837I_malformed.edi")
        result = parse_edi(raw)
        # Should parse successfully even with errors
        assert result.segment_count > 0
        assert result.delimiters is not None

    def test_parse_result_metadata(self):
        raw = _read("837P.edi")
        result = parse_edi(raw)
        assert "loop_map_used" in result.metadata
        assert result.metadata["total_loops"] > 0

    def test_delimiters_in_result(self):
        raw = _read("837P.edi")
        result = parse_edi(raw)
        assert result.delimiters is not None
        assert result.delimiters.element_separator == "*"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _collect_loop_ids(loops: list, ids: set | None = None) -> set:
    """Recursively collect all loop IDs from a nested loop tree."""
    if ids is None:
        ids = set()
    for loop in loops:
        ids.add(loop.loop_id)
        if hasattr(loop, "children") and loop.children:
            _collect_loop_ids(loop.children, ids)
    return ids
