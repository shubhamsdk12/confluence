# SNIP Levels 1-3: Technical Validation Logic

[cite_start]This document defines the Strategic National Implementation Process (SNIP) validation rules required for the US Healthcare EDI Parser[cite: 31, 35].

---

## SNIP Level 1: EDI Syntax Integrity
[cite_start]**Goal:** Ensure the file is a valid X12 envelope[cite: 43].

* [cite_start]**Envelope Structure**: Must contain nested segments: `ISA` -> `GS` -> `ST` -> [Data] -> `SE` -> `GE` -> `IEA`[cite: 43, 71].
* **Control Number Matching**: 
    * [cite_start]`ISA13` (Interchange Control Number) must match `IEA02`[cite: 71].
    * [cite_start]`ST02` (Transaction Set Control Number) must match `SE02`[cite: 71].
* [cite_start]**Segment Counting**: `SE01` must equal the total count of segments between `ST` and `SE` (inclusive)[cite: 44].

## SNIP Level 2: HIPAA Implementation Compliance
[cite_start]**Goal:** Validate formats and mandatory data elements[cite: 48, 49].

* [cite_start]**NPI Validation**: Must be 10 digits and pass the **Luhn Algorithm** check (Segment `NM109`)[cite: 50, 85].
* [cite_start]**Date Formats**: All dates must strictly follow `CCYYMMDD` (Segment `DTP`)[cite: 50, 71].
* [cite_start]**Postal Codes**: ZIP codes must be 5 or 9 digits (Segment `N403`)[cite: 50].
* **Mandatory Segments**:
    * [cite_start]**837**: `BHT`, `NM1` (81/85/PR), `CLM`[cite: 51, 71].
    * [cite_start]**835**: `BPR`, `TRN`, `CLP`[cite: 53, 63].
    * [cite_start]**834**: `BGN`, `INS`, `REF` (0F/1L)[cite: 54, 71].

## SNIP Level 3: Cross-Segment Balancing
[cite_start]**Goal:** Verify mathematical integrity across the transaction[cite: 52].

* **837 Claim Balancing**: 
  $$Total\_Claim\_Charge\_(CLM02) = \sum(Service\_Line\_Charges\_(SV102/SV203))$$
* **835 Payment Reconciliation**:
  $$Total\_Paid\_(CLP04) = Total\_Billed\_(CLP03) - \sum(Adjustments\_(CAS))$$
* [cite_start]**834 Member Consistency**: Verify that the number of `INS` segments matches the control total in `BGN06` (if present)[cite: 54, 71].