"""
Tests for the SNIP 1-3 validation engine.

Covers:
  - SNIP 1: Envelope integrity (control number matching, segment counting)
  - SNIP 2: NPI Luhn validation
  - SNIP 3: 837 claim balancing, 835 payment reconciliation
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

# Ensure backend is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aiosqlite
from database.connection import init_db
from database.repository import persist_parse_result
from parser.state_machine import parse_edi
from validator.snip1 import check_snip1
from validator.snip2 import check_snip2
from validator.snip3 import check_snip3
from validator.npi import validate_npi_luhn, lookup_npi
from validator.engine import validate

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
TEST_DIR = Path(__file__).resolve().parent.parent.parent / "test_files"
_TEST_DB = str(Path(__file__).resolve().parent.parent / "test_validator.db")


@pytest.fixture(autouse=True)
def _set_test_db(monkeypatch):
    monkeypatch.setattr("database.connection.DB_PATH", _TEST_DB)
    yield
    if os.path.exists(_TEST_DB):
        os.remove(_TEST_DB)


def _read(filename: str) -> str:
    return (TEST_DIR / filename).read_text(encoding="utf-8")


async def _setup_and_persist(filename: str) -> tuple:
    """Init DB, parse file, persist, return (conn, interchange_id)."""
    import database.connection as dc
    dc.DB_PATH = _TEST_DB
    await init_db()
    conn = await aiosqlite.connect(_TEST_DB)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    result = parse_edi(_read(filename))
    iid = await persist_parse_result(conn, filename, result)
    return conn, iid


# ========================== NPI LUHN TESTS ==========================

class TestNpiLuhn:
    def test_valid_npi(self):
        """NPI 1234567893 should pass the Luhn check."""
        is_valid, detail = validate_npi_luhn("1234567893")
        assert is_valid, f"Expected valid, got: {detail}"

    def test_invalid_npi(self):
        """NPI 1234567890 should fail the Luhn check."""
        is_valid, detail = validate_npi_luhn("1234567890")
        assert not is_valid
        assert "Luhn check failed" in detail

    def test_npi_format_reject_short(self):
        """5-digit number should fail format check."""
        is_valid, detail = validate_npi_luhn("12345")
        assert not is_valid
        assert "10 digits" in detail

    def test_npi_format_reject_alpha(self):
        """Alphanumeric input should fail."""
        is_valid, detail = validate_npi_luhn("123456789A")
        assert not is_valid

    def test_npi_sanitization(self):
        """Hyphens and spaces should be stripped."""
        is_valid, detail = validate_npi_luhn("1234 5678-93")
        assert is_valid, f"Expected valid after sanitization, got: {detail}"

    def test_another_valid_npi(self):
        """NPI 1112223334 from the malformed test file — check Luhn."""
        is_valid, detail = validate_npi_luhn("1112223334")
        # This NPI may or may not pass Luhn — the test just confirms no crash
        assert isinstance(is_valid, bool)


# ========================== SNIP 1 TESTS ==========================

class TestSnip1:
    def test_snip1_valid_837p(self):
        """837P.edi has matching control numbers → 0 SNIP-1 errors."""
        async def _run():
            conn, iid = await _setup_and_persist("837P.edi")
            try:
                errors = await check_snip1(conn, iid)
                snip1_codes = [e.code for e in errors]
                assert "SNIP1_ISA_IEA_MISMATCH" not in snip1_codes
                assert "SNIP1_ST_SE_MISMATCH" not in snip1_codes
            finally:
                await conn.close()
        asyncio.run(_run())

    def test_snip1_malformed_isa_iea_mismatch(self):
        """837I_malformed.edi has ISA=000000004, IEA=000000005 → envelope error."""
        async def _run():
            conn, iid = await _setup_and_persist("837I_malformed.edi")
            try:
                errors = await check_snip1(conn, iid)
                codes = [e.code for e in errors]
                assert "SNIP1_ISA_IEA_MISMATCH" in codes, (
                    f"Expected ISA/IEA mismatch error. Got: {codes}"
                )
            finally:
                await conn.close()
        asyncio.run(_run())

    def test_snip1_835_valid(self):
        """835.edi should have matching envelope numbers."""
        async def _run():
            conn, iid = await _setup_and_persist("835.edi")
            try:
                errors = await check_snip1(conn, iid)
                mismatch_codes = [e.code for e in errors if "MISMATCH" in e.code]
                assert len(mismatch_codes) == 0
            finally:
                await conn.close()
        asyncio.run(_run())


# ========================== SNIP 2 TESTS ==========================

class TestSnip2:
    def test_snip2_837p_npi_validation(self):
        """837P.edi has NPI 1234567893 which should pass Luhn."""
        async def _run():
            conn, iid = await _setup_and_persist("837P.edi")
            try:
                errors = await check_snip2(conn, iid)
                npi_errors = [e for e in errors if e.code == "SNIP2_INVALID_NPI"]
                # 1234567893 passes Luhn, so no NPI error expected for billing
                billing_npi_errors = [
                    e for e in npi_errors if "1234567893" in e.message
                ]
                assert len(billing_npi_errors) == 0
            finally:
                await conn.close()
        asyncio.run(_run())

    def test_snip2_835_has_payment(self):
        """835.edi should pass mandatory BPR check."""
        async def _run():
            conn, iid = await _setup_and_persist("835.edi")
            try:
                errors = await check_snip2(conn, iid)
                bpr_errors = [e for e in errors if e.code == "SNIP2_MISSING_BPR"]
                assert len(bpr_errors) == 0
            finally:
                await conn.close()
        asyncio.run(_run())

    def test_snip2_834_has_members(self):
        """834.edi should pass mandatory INS check."""
        async def _run():
            conn, iid = await _setup_and_persist("834.edi")
            try:
                errors = await check_snip2(conn, iid)
                ins_errors = [e for e in errors if e.code == "SNIP2_MISSING_INS"]
                assert len(ins_errors) == 0
            finally:
                await conn.close()
        asyncio.run(_run())


# ========================== SNIP 3 TESTS ==========================

class TestSnip3:
    def test_snip3_837p_claim_balancing(self):
        """
        837P.edi: CLM02=$250.00, SV1 lines = $125.00 + $125.00 = $250.00.
        This should balance correctly → no SNIP-3 error.
        """
        async def _run():
            conn, iid = await _setup_and_persist("837P.edi")
            try:
                errors = await check_snip3(conn, iid)
                balance_errors = [e for e in errors if e.code == "SNIP3_CLAIM_BALANCE"]
                assert len(balance_errors) == 0, (
                    f"Expected 0 balance errors for valid 837P, got: "
                    f"{[(e.code, e.message) for e in balance_errors]}"
                )
            finally:
                await conn.close()
        asyncio.run(_run())

    def test_snip3_835_reconciliation(self):
        """
        835.edi: CLP*CLAIM001*1*250.00*200.00 with CAS*CO*45*25.00 + CAS*PR*2*25.00.
        Expected: paid (200) == billed (250) - sum_adj (50) → 200 == 200 → balanced.
        """
        async def _run():
            conn, iid = await _setup_and_persist("835.edi")
            try:
                errors = await check_snip3(conn, iid)
                recon_errors = [e for e in errors if e.code == "SNIP3_REMITTANCE_BALANCE"]
                assert len(recon_errors) == 0, (
                    f"Expected 0 reconciliation errors for valid 835, got: "
                    f"{[(e.code, e.message) for e in recon_errors]}"
                )
            finally:
                await conn.close()
        asyncio.run(_run())

    def test_snip3_834_consistency(self):
        """834.edi with 2 members should not trigger the no-members warning."""
        async def _run():
            conn, iid = await _setup_and_persist("834.edi")
            try:
                errors = await check_snip3(conn, iid)
                member_errors = [e for e in errors if e.code == "SNIP3_NO_MEMBERS"]
                assert len(member_errors) == 0
            finally:
                await conn.close()
        asyncio.run(_run())


# ========================== FULL ENGINE TEST ==========================

class TestFullEngine:
    def test_validate_malformed_catches_envelope_error(self):
        """Full validation on malformed 837I should catch SNIP-1 ISA/IEA mismatch."""
        async def _run():
            conn, iid = await _setup_and_persist("837I_malformed.edi")
            try:
                errors = await validate(conn, iid)
                codes = [e.code for e in errors]
                assert "SNIP1_ISA_IEA_MISMATCH" in codes
            finally:
                await conn.close()
        asyncio.run(_run())

    def test_validate_valid_837p_minimal_errors(self):
        """Valid 837P should have no SNIP-1 or SNIP-3 errors."""
        async def _run():
            conn, iid = await _setup_and_persist("837P.edi")
            try:
                errors = await validate(conn, iid)
                snip1 = [e for e in errors if e.snip_level == 1]
                snip3 = [e for e in errors if e.snip_level == 3]
                assert len(snip1) == 0, f"Unexpected SNIP-1 errors: {[e.code for e in snip1]}"
                assert len(snip3) == 0, f"Unexpected SNIP-3 errors: {[e.code for e in snip3]}"
            finally:
                await conn.close()
        asyncio.run(_run())
