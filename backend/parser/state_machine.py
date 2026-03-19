"""
O(n) single-pass state-machine parser for X12 EDI files.

Converts flat ASCII-delimited text into a hierarchical JSON Loop structure.
Loop boundaries are driven by JSON config files (loop_maps/) rather than
hard-coded logic, per the user's config-driven requirement.

Algorithm:
  1. Split raw text by segment terminator.
  2. For each segment, split by element separator to get elements.
  3. Check if the segment triggers a new loop (via loop map look-up).
  4. Push/pop the loop stack to maintain proper nesting.
  5. Attach the segment to the currently active loop.

Complexity: O(n) where n = number of segments.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from parser.delimiters import extract_delimiters
from parser.identifier import identify_transaction
from parser.models import (
    Delimiters,
    Element,
    Loop,
    ParseResult,
    Segment,
    TransactionType,
)


# ---------------------------------------------------------------------------
# Loop map loader
# ---------------------------------------------------------------------------
_LOOP_MAPS_DIR = Path(__file__).parent / "loop_maps"

_TX_TO_FILE = {
    TransactionType.CLAIM_837P: "837p_loops.json",
    TransactionType.CLAIM_837I: "837i_loops.json",
    TransactionType.REMITTANCE_835: "835_loops.json",
    TransactionType.ENROLLMENT_834: "834_loops.json",
}


class LoopRule:
    """A single loop-trigger rule loaded from the JSON config."""

    def __init__(self, data: dict[str, Any]):
        self.loop_id: str = data["loop_id"]
        self.trigger_segment: str = data["trigger_segment"]
        self.qualifier_position: int | None = data.get("qualifier_position")
        self.qualifier_value: str | None = data.get("qualifier_value")
        self.ui_label: str = data.get("ui_label", self.loop_id)
        self.parent: str | None = data.get("parent")


def load_loop_rules(tx_type: TransactionType) -> list[LoopRule]:
    """Load loop rules from the appropriate JSON config file."""
    filename = _TX_TO_FILE.get(tx_type)
    if not filename:
        return []
    filepath = _LOOP_MAPS_DIR / filename
    if not filepath.exists():
        return []
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [LoopRule(entry) for entry in data.get("loops", [])]


# ---------------------------------------------------------------------------
# Segment parsing helpers
# ---------------------------------------------------------------------------
def _parse_elements(raw_elements: list[str], sub_sep: str) -> list[Element]:
    """Convert raw element strings into Element models (with sub-element splitting)."""
    elements: list[Element] = []
    for idx, val in enumerate(raw_elements):
        sub_elems = val.split(sub_sep) if sub_sep and sub_sep in val else []
        elements.append(
            Element(
                position=idx,
                value=val,
                sub_elements=sub_elems if sub_elems else [],
            )
        )
    return elements


def _match_loop_rule(
    seg_id: str,
    elements: list[str],
    rules: list[LoopRule],
) -> LoopRule | None:
    """
    Check whether a segment triggers a new loop.

    Matching logic:
      1. The segment ID must match the rule's trigger_segment.
      2. If the rule has a qualifier_position and qualifier_value, the element
         at that position must match the qualifier_value.
      3. Return the FIRST matching rule (order in the config is significant).
    """
    for rule in rules:
        if seg_id.upper() != rule.trigger_segment.upper():
            continue
        # If no qualifier required, it's a match
        if rule.qualifier_position is None or rule.qualifier_value is None:
            return rule
        # Qualifier check
        qpos = rule.qualifier_position
        if qpos < len(elements) and elements[qpos].strip().upper() == rule.qualifier_value.upper():
            return rule
    return None


# ---------------------------------------------------------------------------
# Main parser
# ---------------------------------------------------------------------------
def parse_edi(raw: str) -> ParseResult:
    """
    Parse a raw EDI file into a hierarchical ParseResult.

    This is the main entry point. It:
      1. Extracts delimiters from ISA.
      2. Identifies the transaction type.
      3. Loads the appropriate loop-map config.
      4. Performs a single-pass parse building nested loops.

    Args:
        raw: The full raw EDI file content as a string.

    Returns:
        A ParseResult with the hierarchical loop/segment tree.
    """
    # Step 1 — Delimiters
    delimiters = extract_delimiters(raw)

    # Step 2 — Identify transaction
    tx_type, envelope = identify_transaction(raw, delimiters)

    # Step 3 — Load loop rules
    rules = load_loop_rules(tx_type)

    # Step 4 — Split into raw segments
    seg_term = delimiters.segment_terminator
    elem_sep = delimiters.element_separator
    sub_sep = delimiters.sub_element_separator

    raw_segments = [s.strip() for s in raw.split(seg_term) if s.strip()]

    # Step 5 — Single-pass tree construction
    root_loops: list[Loop] = []
    loop_stack: list[Loop] = []  # Stack tracks current nesting context
    # Map of loop_id → Loop for parent look-up
    loop_registry: dict[str, Loop] = {}

    segment_count = 0

    for line_num, seg_raw in enumerate(raw_segments, start=1):
        elements_raw = seg_raw.split(elem_sep)
        seg_id = elements_raw[0].strip().upper()

        # Skip empty
        if not seg_id:
            continue

        segment_count += 1

        # Build the Segment model
        segment = Segment(
            segment_id=seg_id,
            elements=_parse_elements(elements_raw, sub_sep),
            raw=seg_raw,
            line_number=line_num,
        )

        # Check for loop trigger
        matched_rule = _match_loop_rule(seg_id, elements_raw, rules)

        if matched_rule:
            new_loop = Loop(
                loop_id=matched_rule.loop_id,
                ui_label=matched_rule.ui_label,
                segments=[segment],
            )

            # Determine where to attach this loop
            if matched_rule.parent is None:
                # Top-level loop
                _pop_to_root(loop_stack)
                root_loops.append(new_loop)
                loop_stack = [new_loop]
            elif matched_rule.parent in loop_registry:
                # Pop stack until we find the parent
                _pop_to_parent(loop_stack, matched_rule.parent, loop_registry)
                parent_loop = loop_registry[matched_rule.parent]
                parent_loop.children.append(new_loop)
                loop_stack.append(new_loop)
            else:
                # Parent not yet seen — attach to current context or root
                if loop_stack:
                    loop_stack[-1].children.append(new_loop)
                else:
                    root_loops.append(new_loop)
                loop_stack.append(new_loop)

            loop_registry[matched_rule.loop_id] = new_loop
            # Assign UI label to the segment
            segment.ui_label = matched_rule.ui_label
        else:
            # Attach segment to the current active loop
            if loop_stack:
                loop_stack[-1].segments.append(segment)
            else:
                # Orphaned segment before any loop — create a fallback
                fallback = Loop(
                    loop_id="HEADER",
                    ui_label="Header",
                    segments=[segment],
                )
                root_loops.append(fallback)
                loop_stack.append(fallback)
                loop_registry["HEADER"] = fallback

    return ParseResult(
        transaction_type=tx_type,
        envelope=envelope,
        loops=root_loops,
        segment_count=segment_count,
        raw_segment_count=len(raw_segments),
        delimiters=delimiters,
        metadata={
            "loop_map_used": _TX_TO_FILE.get(tx_type, "none"),
            "total_loops": len(loop_registry),
        },
    )


# ---------------------------------------------------------------------------
# Stack helpers
# ---------------------------------------------------------------------------
def _pop_to_root(stack: list[Loop]) -> None:
    """Clear the stack (used when entering a top-level loop)."""
    stack.clear()


def _pop_to_parent(
    stack: list[Loop],
    parent_id: str,
    registry: dict[str, Loop],
) -> None:
    """
    Pop the stack until the top matches the target parent_id.
    If the parent is not on the stack, we leave the stack as-is (the parent
    is still accessible via the registry).
    """
    while stack and stack[-1].loop_id != parent_id:
        stack.pop()
