# X12 EDI Mapping Reference (837, 835, 834)

[cite_start]This reference maps technical segments to human-readable values for the interactive UI tree[cite: 45, 47].

---

## [cite_start]837 - Professional/Institutional Claims [cite: 31, 39]
| Loop | Segment | UI Label | Key Element |
| :--- | :--- | :--- | :--- |
| 1000A | NM1 | Submitter | NM103 (Org Name) |
| 2010BA | NM1 | Subscriber | NM103 (Last Name), NM109 (Member ID) |
| 2300 | CLM | Claim Detail | CLM01 (Patient Acct), CLM02 (Total Billed) |
| 2300 | HI | Diagnosis | HI01-2 (ICD-10 Code) |
| 2400 | SV1/SV2 | Service Line | SV101 (CPT/HCPCS), SV102 (Line Charge) |

## [cite_start]835 - Claim Payment/Remittance [cite: 31, 63]
| Loop | Segment | UI Label | Key Element |
| :--- | :--- | :--- | :--- |
| Header | BPR | Financials | BPR02 (Payment Amt), BPR16 (Check Date) |
| 2100 | CLP | Claim Status | CLP01 (Claim ID), CLP03 (Billed), CLP04 (Paid) |
| 2100 | CAS | Adjustments | CAS01 (Group), CAS02 (Reason Code) |
| 2110 | SVC | Service Payment | SVC01 (CPT Code), SVC02 (Line Paid) |

## [cite_start]834 - Member Enrollment [cite: 31, 65]
| Loop | Segment | UI Label | Key Element |
| :--- | :--- | :--- | :--- |
| 2000 | INS | Member Detail | INS01 (Y=Self), INS03 (021=Add, 024=Term) |
| 2100A | NM1 | Member Name | NM103 (Last), NM104 (First), NM109 (SSN) |
| 2300 | HD | Coverage | HD03 (Insurance Type - e.g., FAM/EMP) |
| 2300 | DTP | Dates | DTP03 (Benefit Start/End Date) |

---

### [cite_start]AI Implementation Notes[cite: 59, 93]:
1. **Dynamic Labels**: Use the "UI Label" column to replace raw segment IDs in the collapsible tree.
2. **Contextual Search**: When a user asks about an error in Loop 2300, search this document for "837" and "2300" to provide the specific context for the `CLM` segment.