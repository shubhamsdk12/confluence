"""
NPI Validation — Luhn Algorithm + CMS NPPES API.

Implementation follows npi_lookup_guide.md exactly:
  1. Format check: must be exactly 10 digits.
  2. Luhn check: prepend "80840" to first 9 digits → Mod-10 → compare to 10th digit.
  3. If Luhn passes → CMS NPPES API lookup with caching.

Reference: npi_lookup_guide.md
"""
from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

import httpx

# ---------------------------------------------------------------------------
# Local Luhn Validation
# ---------------------------------------------------------------------------

_NPI_RE = re.compile(r"^\d{10}$")


def validate_npi_luhn(npi: str) -> tuple[bool, str]:
    """
    Validate an NPI using the Luhn algorithm per CMS spec.

    The healthcare Luhn variant prepends "80840" to ALL 10 digits
    of the NPI (producing a 15-digit payload), then runs a standard
    Luhn validation: the total sum mod 10 must equal 0.

    Args:
        npi: The NPI string (may contain hyphens/spaces — will be sanitized).

    Returns:
        Tuple of (is_valid, detail_message).
    """
    # Sanitize: remove hyphens, spaces
    clean = re.sub(r"[\s\-]", "", npi)

    # Format check
    if not _NPI_RE.match(clean):
        return False, f"NPI must be exactly 10 digits, got '{clean}' ({len(clean)} chars)"

    # Prepend "80840" to ALL 10 digits per CMS spec → 15-digit payload
    payload = "80840" + clean  # 15-digit string

    # Standard Luhn Mod-10 validation
    digits = [int(d) for d in payload]
    # Process from right to left; double every second digit from the right
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            doubled = d * 2
            total += doubled - 9 if doubled > 9 else doubled
        else:
            total += d

    # Valid if total is divisible by 10
    if total % 10 != 0:
        return False, (
            f"Luhn check failed: sum mod 10 = {total % 10} (expected 0)"
        )

    return True, "Valid NPI (Luhn check passed)"


# ---------------------------------------------------------------------------
# CMS NPPES API Lookup
# ---------------------------------------------------------------------------

_NPPES_URL = "https://npiregistry.cms.hhs.gov/api/"


@lru_cache(maxsize=256)
def _cached_nppes_lookup(npi: str) -> dict[str, Any]:
    """
    Synchronous NPPES API call (cached).
    Uses httpx sync client for simplicity in the LRU cache.
    """
    try:
        resp = httpx.get(
            _NPPES_URL,
            params={"number": npi, "version": "2.1"},
            timeout=10.0,
        )
        resp.raise_for_status()
        return resp.json()
    except (httpx.HTTPError, Exception) as e:
        return {"error": str(e)}


def lookup_npi(npi: str) -> dict[str, Any]:
    """
    Full NPI validation: Luhn check first, then NPPES API lookup.

    Fail-fast: if Luhn fails, returns immediately without calling the API.

    Returns:
        Dict with: npi, valid_luhn, luhn_detail, found_in_nppes,
                    provider_name, specialty, practice_state, status.
    """
    clean = re.sub(r"[\s\-]", "", npi)

    result: dict[str, Any] = {
        "npi": clean,
        "valid_luhn": False,
        "luhn_detail": "",
        "found_in_nppes": False,
        "provider_name": "",
        "specialty": "",
        "practice_state": "",
        "status": "",
    }

    # Step 1: Luhn check (fail-fast)
    is_valid, detail = validate_npi_luhn(clean)
    result["valid_luhn"] = is_valid
    result["luhn_detail"] = detail

    if not is_valid:
        return result

    # Step 2: NPPES API lookup
    data = _cached_nppes_lookup(clean)
    if "error" in data:
        result["luhn_detail"] += f" | NPPES error: {data['error']}"
        return result

    results_list = data.get("results") or []
    if not results_list:
        return result

    provider = results_list[0]
    result["found_in_nppes"] = True

    basic = provider.get("basic", {})
    result["status"] = basic.get("status", "")

    # Name: individual or organization
    org_name = basic.get("organization_name", "")
    first = basic.get("first_name", "")
    last = basic.get("last_name", "")
    result["provider_name"] = org_name if org_name else f"{first} {last}".strip()

    # Primary taxonomy
    taxonomies = provider.get("taxonomies", [])
    for tax in taxonomies:
        if tax.get("primary"):
            result["specialty"] = tax.get("desc", "")
            break

    # Practice state
    addresses = provider.get("addresses", [])
    if addresses:
        result["practice_state"] = addresses[0].get("state", "")

    return result
