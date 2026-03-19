"""
Tests for the database persistence layer.

Verifies that parsed EDI data is correctly persisted to SQLite tables.
"""
import asyncio
import os
import sys
from pathlib import Path

import pytest

# Ensure backend is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import aiosqlite
from database.connection import init_db, DB_PATH
from database.repository import persist_parse_result
from parser.state_machine import parse_edi

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
TEST_DIR = Path(__file__).resolve().parent.parent.parent / "test_files"
_TEST_DB = str(Path(__file__).resolve().parent.parent / "test_edi_data.db")


@pytest.fixture(autouse=True)
def _set_test_db(monkeypatch):
    """Use a separate test database, deleted after each test."""
    monkeypatch.setattr("database.connection.DB_PATH", _TEST_DB)
    yield
    if os.path.exists(_TEST_DB):
        os.remove(_TEST_DB)


@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


def _read(filename: str) -> str:
    return (TEST_DIR / filename).read_text(encoding="utf-8")


async def _setup_db():
    """Initialize test database and return connection."""
    # We need to patch DB_PATH before calling init_db
    import database.connection as dc
    dc.DB_PATH = _TEST_DB
    await init_db()
    conn = await aiosqlite.connect(_TEST_DB)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


# ---------------------------------------------------------------------------
# Schema Tests
# ---------------------------------------------------------------------------

class TestSchema:
    def test_schema_creation(self):
        async def _run():
            conn = await _setup_db()
            try:
                rows = await conn.execute_fetchall(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = {dict(r)["name"] for r in rows}
                expected = {
                    "interchanges", "claims", "service_lines",
                    "payments", "remittance_claims", "adjustments",
                    "members", "validation_errors",
                }
                assert expected.issubset(tables), f"Missing tables: {expected - tables}"
            finally:
                await conn.close()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# 837 Persistence Tests
# ---------------------------------------------------------------------------

class TestPersist837:
    def test_persist_837p_interchange(self):
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("837P.edi"))
                iid = await persist_parse_result(conn, "837P.edi", result)
                assert iid is not None and iid > 0

                rows = await conn.execute_fetchall(
                    "SELECT * FROM interchanges WHERE id = ?", (iid,)
                )
                assert len(rows) == 1
                rec = dict(rows[0])
                assert rec["transaction_type"] == "837P"
                assert rec["isa_control_num"] == "000000001"
            finally:
                await conn.close()

        asyncio.run(_run())

    def test_persist_837p_claims(self):
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("837P.edi"))
                iid = await persist_parse_result(conn, "837P.edi", result)

                rows = await conn.execute_fetchall(
                    "SELECT * FROM claims WHERE interchange_id = ?", (iid,)
                )
                assert len(rows) >= 1, "Should have at least one claim"

                claim = dict(rows[0])
                assert float(claim["total_charge"]) > 0
                assert claim["patient_control_num"] == "CLAIM001"
            finally:
                await conn.close()

        asyncio.run(_run())

    def test_persist_837p_service_lines(self):
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("837P.edi"))
                iid = await persist_parse_result(conn, "837P.edi", result)

                rows = await conn.execute_fetchall(
                    "SELECT * FROM service_lines WHERE interchange_id = ?", (iid,)
                )
                assert len(rows) >= 1, "Should have at least one service line"

                for r in rows:
                    sl = dict(r)
                    assert float(sl["line_charge"]) > 0
            finally:
                await conn.close()

        asyncio.run(_run())

    def test_persist_837p_billing_npi(self):
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("837P.edi"))
                iid = await persist_parse_result(conn, "837P.edi", result)

                rows = await conn.execute_fetchall(
                    "SELECT billing_npi FROM claims WHERE interchange_id = ?", (iid,)
                )
                claim = dict(rows[0])
                assert claim["billing_npi"] == "1234567893"
            finally:
                await conn.close()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# 835 Persistence Tests
# ---------------------------------------------------------------------------

class TestPersist835:
    def test_persist_835_payment(self):
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("835.edi"))
                iid = await persist_parse_result(conn, "835.edi", result)

                rows = await conn.execute_fetchall(
                    "SELECT * FROM payments WHERE interchange_id = ?", (iid,)
                )
                assert len(rows) >= 1
                payment = dict(rows[0])
                assert float(payment["total_payment"]) == 375.00
            finally:
                await conn.close()

        asyncio.run(_run())

    def test_persist_835_remittance_claims(self):
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("835.edi"))
                iid = await persist_parse_result(conn, "835.edi", result)

                rows = await conn.execute_fetchall(
                    "SELECT * FROM remittance_claims WHERE interchange_id = ?", (iid,)
                )
                assert len(rows) >= 1
                rc = dict(rows[0])
                assert rc["claim_id_ref"] == "CLAIM001"
                assert float(rc["billed_amount"]) == 250.00
                assert float(rc["paid_amount"]) == 200.00
            finally:
                await conn.close()

        asyncio.run(_run())

    def test_persist_835_adjustments(self):
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("835.edi"))
                iid = await persist_parse_result(conn, "835.edi", result)

                rows = await conn.execute_fetchall(
                    """SELECT a.* FROM adjustments a
                       JOIN remittance_claims rc ON rc.id = a.remittance_claim_id
                       WHERE rc.interchange_id = ?""",
                    (iid,),
                )
                assert len(rows) >= 1, "Should have at least one adjustment"
                # The 835 test file has CAS*CO*45*25.00 and CAS*PR*2*25.00
                codes = {dict(r)["reason_code"] for r in rows}
                assert "45" in codes or "2" in codes
            finally:
                await conn.close()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# 834 Persistence Tests
# ---------------------------------------------------------------------------

class TestPersist834:
    def test_persist_834_members(self):
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("834.edi"))
                iid = await persist_parse_result(conn, "834.edi", result)

                rows = await conn.execute_fetchall(
                    "SELECT * FROM members WHERE interchange_id = ?", (iid,)
                )
                assert len(rows) >= 2, "Should have at least 2 members (SMITH + JONES)"

                subs = {dict(r)["subscriber_id"] for r in rows}
                assert "SUBSCRIBER001" in subs
                assert "SUBSCRIBER002" in subs
            finally:
                await conn.close()

        asyncio.run(_run())

    def test_persist_834_member_details(self):
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("834.edi"))
                iid = await persist_parse_result(conn, "834.edi", result)

                rows = await conn.execute_fetchall(
                    "SELECT * FROM members WHERE interchange_id = ? AND subscriber_id = 'SUBSCRIBER001'",
                    (iid,),
                )
                assert len(rows) == 1
                m = dict(rows[0])
                assert m["last_name"] == "SMITH"
                assert m["first_name"] == "ALICE"
                assert m["maintenance_code"] == "021"
            finally:
                await conn.close()

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# Envelope Control Number Tests
# ---------------------------------------------------------------------------

class TestEnvelope:
    def test_envelope_control_numbers(self):
        """Verify ISA/IEA control numbers are stored correctly for SNIP-1."""
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("837P.edi"))
                iid = await persist_parse_result(conn, "837P.edi", result)

                rows = await conn.execute_fetchall(
                    "SELECT isa_control_num, iea_control_num FROM interchanges WHERE id = ?",
                    (iid,),
                )
                rec = dict(rows[0])
                assert rec["isa_control_num"] == "000000001"
                assert rec["iea_control_num"] == "000000001"
            finally:
                await conn.close()

        asyncio.run(_run())

    def test_malformed_envelope_mismatch(self):
        """The 837I_malformed file has ISA=000000004 but IEA=000000005."""
        async def _run():
            conn = await _setup_db()
            try:
                result = parse_edi(_read("837I_malformed.edi"))
                iid = await persist_parse_result(conn, "837I_malformed.edi", result)

                rows = await conn.execute_fetchall(
                    "SELECT isa_control_num, iea_control_num FROM interchanges WHERE id = ?",
                    (iid,),
                )
                rec = dict(rows[0])
                assert rec["isa_control_num"] == "000000004"
                assert rec["iea_control_num"] == "000000005"
                assert rec["isa_control_num"] != rec["iea_control_num"]
            finally:
                await conn.close()

        asyncio.run(_run())
