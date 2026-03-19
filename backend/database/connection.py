"""
Database connection management for SQLite.

Provides async connection handling via aiosqlite and schema initialization.
"""
import os
from pathlib import Path

import aiosqlite

# Default DB path — configurable via EDI_DB_PATH env var
_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "edi_data.db"
DB_PATH = os.getenv("EDI_DB_PATH", str(_DEFAULT_DB_PATH))

_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


async def get_db() -> aiosqlite.Connection:
    """Open and return an async SQLite connection with WAL mode and FK enforcement."""
    conn = await aiosqlite.connect(DB_PATH)
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA journal_mode=WAL")
    await conn.execute("PRAGMA foreign_keys=ON")
    return conn


async def init_db() -> None:
    """Create all tables from schema.sql if they don't already exist."""
    ddl = _SCHEMA_PATH.read_text(encoding="utf-8")
    conn = await get_db()
    try:
        await conn.executescript(ddl)
        await conn.commit()
    finally:
        await conn.close()
