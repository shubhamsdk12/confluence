"""
Pydantic v2 data models for the EDI parser.

Defines the core structures: Segment, Loop, ParsedTransaction, ParseResult.
"""
from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class TransactionType(str, Enum):
    """Supported X12 transaction types."""
    CLAIM_837P = "837P"
    CLAIM_837I = "837I"
    REMITTANCE_835 = "835"
    ENROLLMENT_834 = "834"
    UNKNOWN = "UNKNOWN"


class Severity(str, Enum):
    """Validation error severity levels."""
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


# ---------------------------------------------------------------------------
# Delimiter model
# ---------------------------------------------------------------------------
class Delimiters(BaseModel):
    """X12 delimiters extracted from the ISA segment."""
    element_separator: str = Field(..., description="Element (field) separator, typically '*'")
    sub_element_separator: str = Field(..., description="Sub-element (component) separator, typically ':'")
    segment_terminator: str = Field(..., description="Segment terminator, typically '~'")


# ---------------------------------------------------------------------------
# Parsed structures
# ---------------------------------------------------------------------------
class Element(BaseModel):
    """A single data element within a segment."""
    position: int = Field(..., description="0-based position within the segment")
    value: str = Field(..., description="Raw value of the element")
    sub_elements: list[str] = Field(default_factory=list, description="Sub-element values if composite")


class Segment(BaseModel):
    """A parsed EDI segment (e.g. NM1*85*1*DOE*JOHN...)."""
    segment_id: str = Field(..., description="Segment identifier, e.g. 'NM1', 'CLM'")
    elements: list[Element] = Field(default_factory=list)
    raw: str = Field("", description="Original raw text of the segment")
    line_number: int = Field(0, description="1-based line/position in original file")
    ui_label: str = Field("", description="Human-readable label from edi_mapping_reference")


class Loop(BaseModel):
    """A hierarchical loop containing segments and child loops."""
    loop_id: str = Field(..., description="Loop identifier, e.g. '2000A', '2300'")
    ui_label: str = Field("", description="Human-readable label for the UI tree")
    segments: list[Segment] = Field(default_factory=list)
    children: list[Loop] = Field(default_factory=list)


class EnvelopeInfo(BaseModel):
    """Metadata extracted from ISA/GS/ST envelope segments."""
    interchange_control_number: str = ""
    sender_id: str = ""
    receiver_id: str = ""
    functional_group_control_number: str = ""
    transaction_set_control_number: str = ""
    gs_code: str = ""
    st_code: str = ""
    isa_date: str = ""
    isa_time: str = ""


class ParseResult(BaseModel):
    """Complete result of parsing an EDI file."""
    transaction_type: TransactionType
    envelope: EnvelopeInfo = Field(default_factory=EnvelopeInfo)
    loops: list[Loop] = Field(default_factory=list)
    segment_count: int = 0
    raw_segment_count: int = Field(0, description="Total number of segments in the file")
    delimiters: Delimiters | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Validation models (used in Phase 2, defined here for forward-compatibility)
# ---------------------------------------------------------------------------
class ValidationError(BaseModel):
    """A single validation error or warning."""
    segment_id: str = ""
    element_position: int | None = None
    loop_id: str = ""
    snip_level: int = Field(..., ge=1, le=3)
    severity: Severity = Severity.ERROR
    code: str = ""
    message: str = ""
    suggestion: str = ""


class ValidationResult(BaseModel):
    """Full validation output bundled with the parse result."""
    parse_result: ParseResult
    errors: list[ValidationError] = Field(default_factory=list)
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
