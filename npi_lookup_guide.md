# NPI Validation & Registry Lookup Specification

This document details the implementation requirements for validating National Provider Identifiers (NPI) using the Luhn Algorithm and the CMS NPPES Registry API.

---

## 1. Local Validation: The Luhn Algorithm
Before calling the external API, the system must perform a local checksum to flag obviously malformed NPIs.

* **Format**: The NPI is a 10-digit numeric identifier.
* **The Checksum Formula**: The 10th digit is a check digit calculated using the Luhn formula.
* **Implementation Note**: In the US healthcare context, the Luhn algorithm is applied to the NPI by **prepending "80840"** to the first 9 digits.
    * **Payload**: `80840` + `[First 9 digits of NPI]`
    * **Logic**: Run the standard Luhn (Mod 10) check on this 14-digit payload. If the resulting check digit matches the 10th digit of the NPI, it is mathematically valid.

## 2. External Validation: CMS NPPES API
Once a number passes the local Luhn check, verify the provider's active status via the official registry.

* **Endpoint**: `https://npiregistry.cms.hhs.gov/api/?version=2.1`
* **Method**: `GET`
* **Key Parameters**:
    * `number`: The 10-digit NPI.
    * `version`: Must be set to `2.1`.

## 3. Data Extraction for UI/RAG
The API returns a nested JSON. The parser should extract the following for the "Interactive Tree" view:

| Data Point | JSON Path | Use Case |
| :--- | :--- | :--- |
| **Provider Name** | `results[0].basic.first_name` / `organization_name` | Identity Verification |
| **Primary Specialty** | `results[0].taxonomies` (where `primary` is true) | Specialty/Taxonomy Check |
| **Practice State** | `results[0].addresses[0].state` | Cross-checking against 837 data |
| **Status** | `results[0].basic.status` | Ensure NPI is "Active" |

---

### Implementation Instructions for Antigravity:
1. **Fail Fast**: If the NPI fails the Luhn check, return an error immediately without calling the API.
2. **Caching**: Implement a simple cache (e.g., Python `functools.lru_cache`) for API results to avoid hitting rate limits.
3. **Sanitization**: Ensure the `number` parameter is a clean string (remove hyphens/spaces) before sending the request.