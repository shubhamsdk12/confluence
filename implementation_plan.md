# US Healthcare EDI Parser & X12 File Validator — 4-Phase Implementation Plan

A high-performance hackathon prototype that parses, validates, and provides AI-driven explanations for X12 EDI healthcare transactions (837P/I, 835, 834). Designed for demo-ready impact: deterministic parsing first, then layered validation, AI intelligence, and differentiating features.

> [!IMPORTANT]
> **Constraint Alignment**: Every design decision below is derived from the three project constraint files ([.cursorrules](file:///c:/Users/ryan/OneDrive/Desktop/COEP/.cursorrules), [architecture.md](file:///c:/Users/ryan/OneDrive/Desktop/COEP/architecture.md), [knowledge_index_rules.json](file:///c:/Users/ryan/OneDrive/Desktop/COEP/knowledge_index_rules.json)). Deviations are called out explicitly.

---

## Proposed Changes

### Phase 1 — The Foundation (Ingestion & Parsing)

**Goal**: Stand up the full-stack skeleton and build the core state-machine parser that converts raw EDI flat-files into navigable JSON.

---

#### 1.1 Project Scaffolding

##### Backend (`/backend`)

###### [NEW] [main.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/main.py)
- FastAPI application entry point.
- CORS middleware configured for the React dev server (`http://localhost:5173`).
- Global exception handler returning structured `{ detail, code }` JSON.

###### [NEW] [requirements.txt](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/requirements.txt)
- Pin: `fastapi`, `uvicorn[standard]`, `python-multipart`, `pydantic>=2`, `httpx`, `langchain`, `chromadb`, `openai`.

##### Frontend (`/frontend`)

###### [NEW] Vite + React + TypeScript scaffold
- Created via `npx -y create-vite@latest ./ --template react-ts`.
- Install TailwindCSS v3 per [.cursorrules](file:///c:/Users/ryan/OneDrive/Desktop/COEP/.cursorrules) mandate (`React + TypeScript + TailwindCSS`).
- Add `react-json-tree` (or `react-d3-tree`) for Phase 2's interactive tree.

##### Shared

###### [NEW] [test_files/](file:///c:/Users/ryan/OneDrive/Desktop/COEP/test_files/)
- Directory holding the four judge-provided EDI samples: `837P.edi`, `835.edi`, `834.edi`, `837I_malformed.edi`.
- These files will be used for every phase's verification.

---

#### 1.2 Core State-Machine Parser

> [!NOTE]
> Per [.cursorrules](file:///c:/Users/ryan/OneDrive/Desktop/COEP/.cursorrules) §Implementation Principles #1: *"Always use pure code (Regex/State Machines) for structural parsing."* No AI or LLM is used here.

###### [NEW] [backend/parser/delimiters.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/parser/delimiters.py)
- Extract delimiters from the ISA segment (fixed-width positions):
  - **Element separator** → `ISA[3]` (typically `*`)
  - **Sub-element separator** → `ISA[104]` (typically `:`)
  - **Segment terminator** → `ISA[105]` (typically `~`)
- Return a `Delimiters` Pydantic model.

###### [NEW] [backend/parser/identifier.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/parser/identifier.py)
- **Transaction Type Auto-Detection** (per [architecture.md](file:///c:/Users/ryan/OneDrive/Desktop/COEP/architecture.md) §1):
  - Read `GS01` (Functional Group Code) and `ST01` (Transaction Set ID).
  - Map: `ST01=837 + GS01=HC` → 837P, `ST01=837 + GS01=HI` → 837I (institutional), `ST01=835` → Remittance, `ST01=834` → Enrollment.
  - Return enum `TransactionType.CLAIM_837P | CLAIM_837I | REMITTANCE_835 | ENROLLMENT_834`.

###### [NEW] [backend/parser/state_machine.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/parser/state_machine.py)
- **O(n) single-pass parser**:
  1. Split raw text by segment terminator.
  2. For each segment, split by element separator.
  3. Identify loop boundaries using segment IDs + qualifier look-ahead (e.g., `HL*...*20` → Billing Provider loop, `CLM` → Claim Detail loop).
  4. Build a nested Python dict: `{ "loop_id": "2000A", "segments": [...], "children": [...] }`.
- Transaction-type-specific loop maps loaded from JSON config files:

###### [NEW] [backend/parser/loop_maps/](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/parser/loop_maps/)
- `837p_loops.json`, `837i_loops.json`, `835_loops.json`, `834_loops.json`
- Each file defines: loop trigger segment, qualifier position, qualifier value, parent loop.
- Example entry: `{ "loop": "2010AA", "trigger": "NM1", "qualifier_pos": 1, "qualifier_val": "85", "parent": "2000A" }`

###### [NEW] [backend/parser/models.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/parser/models.py)
- Pydantic v2 models: `Segment`, `Loop`, `ParsedTransaction`, `ParseResult`.
- `ParseResult` includes: `transaction_type`, `interchange_control_number`, `sender_id`, `receiver_id`, `root_loops[]`, and `metadata` dict.

---

#### 1.3 Upload & Parse API

###### [NEW] [backend/routes/parse.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/routes/parse.py)
- `POST /api/parse` — accepts `UploadFile`, returns `ParseResult` JSON.
- Flow: `read bytes → detect delimiters → identify type → run state machine → serialize`.
- Max file size guard: 10 MB (configurable via env).

---

### Phase 2 — Validation & UX

**Goal**: Layer SNIP 1-3 validation on top of the parsed tree, integrate live NPI lookups, and build the interactive collapsible tree UI.

---

#### 2.1 JSON-Driven Validation Engine

> [!NOTE]
> Per [architecture.md](file:///c:/Users/ryan/OneDrive/Desktop/COEP/architecture.md) §2 and [knowledge_index_rules.json](file:///c:/Users/ryan/OneDrive/Desktop/COEP/knowledge_index_rules.json): SNIP Levels 1-3, Luhn-based NPI check enabled, claim balance tolerance = $0.01, date format = CCYYMMDD.

###### [NEW] [backend/validator/engine.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/validator/engine.py)
- Generic rule executor: loads rules from JSON, applies each rule to the parsed tree, collects `ValidationError` objects.
- Each `ValidationError`: `{ segment_id, element_pos, snip_level, severity, code, message }`.

###### [NEW] [backend/validator/rules/](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/validator/rules/)
- **`snip1_integrity.json`** — SNIP Level 1 (EDI Syntax Integrity):
  - ISA/IEA envelope balancing (control numbers match, segment counts correct).
  - GS/GE functional group balancing.
  - ST/SE transaction set balancing.
  - Valid segment terminators and element separators.
- **`snip2_requirements.json`** — SNIP Level 2 (Implementation Guide Compliance):
  - Required segments present per transaction type (e.g., CLM required in 837, CLP required in 835).
  - Required elements within segments (e.g., CLM05 Frequency Type Code).
  - Data type validation (numeric, alphanumeric, date CCYYMMDD per [knowledge_index_rules.json](file:///c:/Users/ryan/OneDrive/Desktop/COEP/knowledge_index_rules.json)).
  - Element length min/max checks.
- **`snip3_balancing.json`** — SNIP Level 3 (Balancing):
  - 837: `CLM02` (Charge Amount) sum per claim matches `SBR` level totals.
  - 835: `CLP04` (Payment Amount) sums reconcile against `BPR02` (Total Payment).
  - Tolerance: `$0.01` (from `knowledge_index_rules.json → claim_balance_tolerance`).

###### [NEW] [backend/validator/npi.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/validator/npi.py)
- **Luhn-10 local check** first (per `knowledge_index_rules.json → npi_luhn_check: true`).
- If Luhn passes → **CMS NPPES API** call (`https://npiregistry.cms.hhs.gov/api/?number={npi}&version=2.1`) via `httpx.AsyncClient`.
- Cache NPI results in-memory (dict) for the session to avoid redundant calls.
- Return: `{ npi, valid_luhn, found_in_nppes, provider_name, taxonomy }`.

---

#### 2.2 Validation API

###### [NEW] [backend/routes/validate.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/routes/validate.py)
- `POST /api/validate` — accepts `UploadFile`, returns `{ parse_result, validation_errors[], summary_stats }`.
- Internally calls parser then validator.
- `summary_stats`: error count by SNIP level, error count by severity.

---

#### 2.3 Interactive Collapsible Tree (Frontend)

> [!NOTE]
> Per [.cursorrules](file:///c:/Users/ryan/OneDrive/Desktop/COEP/.cursorrules) §4 and [architecture.md](file:///c:/Users/ryan/OneDrive/Desktop/COEP/architecture.md) §4: *"Prioritize a collapsible, hierarchical tree view."*

###### [NEW] [frontend/src/components/FileUpload.tsx](file:///c:/Users/ryan/OneDrive/Desktop/COEP/frontend/src/components/FileUpload.tsx)
- Drag-and-drop zone accepting `.edi`, `.txt`, `.dat`, `.x12`.
- Calls `POST /api/validate`, stores response in React state.

###### [NEW] [frontend/src/components/EdiTree.tsx](file:///c:/Users/ryan/OneDrive/Desktop/COEP/frontend/src/components/EdiTree.tsx)
- Recursive React component rendering `Loop` nodes as collapsible sections.
- Each segment row shows: segment ID, raw text, and validation error badges (color-coded by severity: 🔴 Error, 🟡 Warning, 🟢 Info).
- Click a segment → side panel shows element-level breakdown.

###### [NEW] [frontend/src/components/ValidationSummary.tsx](file:///c:/Users/ryan/OneDrive/Desktop/COEP/frontend/src/components/ValidationSummary.tsx)
- Dashboard card showing: total errors/warnings, breakdown by SNIP level, pie chart or bar chart of error categories.

###### [NEW] [frontend/src/components/SegmentDetail.tsx](file:///c:/Users/ryan/OneDrive/Desktop/COEP/frontend/src/components/SegmentDetail.tsx)
- Side panel: shows each element with its position, value, data type, and any validation error.
- For NPI elements → shows NPPES lookup result inline.

---

### Phase 3 — AI Intelligence (RAG + MMR)

**Goal**: Index HIPAA reference material, provide plain-English error explanations via RAG with MMR retrieval, and offer a Fix Assistant.

---

#### 3.1 Knowledge Base & Vector Indexing

> [!IMPORTANT]
> Per [knowledge_index_rules.json](file:///c:/Users/ryan/OneDrive/Desktop/COEP/knowledge_index_rules.json): embedding model = `text-embedding-3-small`, retrieval = MMR, λ = 0.5, top_k = 5, source priority = HIPAA 5010 Guide > CMS Manual > WEDI CARC/RARC.

###### [NEW] [backend/ai/indexer.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/ai/indexer.py)
- One-time script to chunk and index HIPAA reference docs.
- **Chunking strategy**: split by section headers (Loop/Segment descriptions), ~500 tokens per chunk, 50-token overlap.
- Store in **ChromaDB** (local persistent mode, per [.cursorrules](file:///c:/Users/ryan/OneDrive/Desktop/COEP/.cursorrules) — ChromaDB/Pinecone).
- Metadata per chunk: `{ source_document, section, loop_id, segment_id, page }`.

###### [NEW] [backend/ai/knowledge_docs/](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/ai/knowledge_docs/)
- Placeholder directory for HIPAA 5010 Implementation Guide excerpts, CMS manuals, and CARC/RARC code lists.
- For hackathon: include curated excerpts covering the segments present in the four test files.

---

#### 3.2 MMR Retriever & Error Explainer

###### [NEW] [backend/ai/retriever.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/ai/retriever.py)
- LangChain `Chroma` vector store + `MMR` search type.
- Parameters from [knowledge_index_rules.json](file:///c:/Users/ryan/OneDrive/Desktop/COEP/knowledge_index_rules.json): `fetch_k=20`, `k=5`, `lambda_mult=0.5`.
- Source priority weighting: boost scores for chunks from higher-priority sources.

###### [NEW] [backend/ai/explainer.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/ai/explainer.py)
- Takes a `ValidationError` → queries retriever → constructs prompt → calls LLM.
- **PHI Masking** (per [.cursorrules](file:///c:/Users/ryan/OneDrive/Desktop/COEP/.cursorrules) §3): Before sending to LLM, strip/replace:
  - Patient names → `[PATIENT]`
  - Dates of birth → `[DOB]`
  - SSNs → `[SSN]`
  - Member IDs → `[MEMBER_ID]`
  - Addresses → `[ADDRESS]`
- Returns: `{ plain_english_explanation, regulatory_context, suggested_fix, sources[] }`.

---

#### 3.3 AI Chat API & Fix Assistant

###### [NEW] [backend/routes/ai.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/routes/ai.py)
- `POST /api/explain` — accepts a `ValidationError`, returns AI explanation.
- `POST /api/chat` — freeform question about the EDI file; retriever fetches relevant context.
- `POST /api/fix` — accepts a `ValidationError` + original segment, returns a corrected segment value.

###### [NEW] [frontend/src/components/AiPanel.tsx](file:///c:/Users/ryan/OneDrive/Desktop/COEP/frontend/src/components/AiPanel.tsx)
- Slide-out panel triggered by clicking "Explain" on any validation error.
- Shows: plain-English explanation, HIPAA regulation excerpt, suggested fix with one-click copy.
- Chat input for follow-up questions scoped to the current file.

---

### Phase 4 — High-Impact Differentiators

**Goal**: Deliver the two standout features that separate this prototype from a basic parser: 835 Reconciliation and 834 Delta Engine.

---

#### 4.1 835-to-837 Reconciliation Engine

> [!NOTE]
> Per [.cursorrules](file:///c:/Users/ryan/OneDrive/Desktop/COEP/.cursorrules) §Feature Focus: *"Match claims to payments using ICN/DCN keys."*

###### [NEW] [backend/reconciliation/engine.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/reconciliation/engine.py)
- Input: one parsed 837P/I + one parsed 835.
- Matching logic:
  1. Extract `CLM01` (Patient Control Number / ICN) from each 837 claim.
  2. Extract `CLP01` (Claim ID / DCN) from each 835 payment.
  3. Match on ICN = DCN (or configurable cross-reference mapping).
- Output per matched claim:
  - `billed_amount` (CLM02) vs `paid_amount` (CLP04).
  - `adjustment_reasons[]` — parsed from CAS segments (CARC + RARC codes).
  - `status`: Paid in Full | Partial | Denied | Unmatched.

###### [NEW] [backend/routes/reconcile.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/routes/reconcile.py)
- `POST /api/reconcile` — accepts two files (837 + 835), returns reconciliation report.

###### [NEW] [frontend/src/components/ReconciliationView.tsx](file:///c:/Users/ryan/OneDrive/Desktop/COEP/frontend/src/components/ReconciliationView.tsx)
- Table: Claim ID | Billed | Paid | Adjustments | Status.
- Color-coded rows: green = paid in full, yellow = partial, red = denied, gray = unmatched.
- Click a row → drills into CAS adjustment reason codes with AI explanation.

---

#### 4.2 834 Delta Engine

> [!NOTE]
> Per [.cursorrules](file:///c:/Users/ryan/OneDrive/Desktop/COEP/.cursorrules) §Feature Focus: *"Compare consecutive enrollment files to identify net changes per member."*

###### [NEW] [backend/delta/engine.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/delta/engine.py)
- Input: two parsed 834 files (e.g., January roster, February roster).
- Comparison logic:
  1. Key each member by `INS` + `REF` (Subscriber ID).
  2. Diff: Added members, Terminated members, Changed members (field-level diff).
  3. Parse `INS01` (Member Indicator) and `INS03` (Maintenance Type Code) for context: `001=Add`, `021=Change`, `024=Terminate`.
- Output: `{ added[], terminated[], changed[], unchanged_count }`.

###### [NEW] [backend/routes/delta.py](file:///c:/Users/ryan/OneDrive/Desktop/COEP/backend/routes/delta.py)
- `POST /api/delta` — accepts two 834 files, returns delta report.

###### [NEW] [frontend/src/components/DeltaView.tsx](file:///c:/Users/ryan/OneDrive/Desktop/COEP/frontend/src/components/DeltaView.tsx)
- **Member roster table** with color-coded maintenance types (per [architecture.md](file:///c:/Users/ryan/OneDrive/Desktop/COEP/architecture.md) §4):
  - 🟢 Green = Added | 🟡 Yellow = Changed | 🔴 Red = Terminated | ⚪ Gray = Unchanged.
- Expand a changed member → shows field-level diff (old value → new value).

---

## Summary of File Structure

```
COEP/
├── .cursorrules
├── architecture.md
├── knowledge_index_rules.json
├── test_files/
│   ├── 837P.edi
│   ├── 835.edi
│   ├── 834.edi
│   └── 837I_malformed.edi
├── backend/
│   ├── main.py
│   ├── requirements.txt
│   ├── parser/
│   │   ├── __init__.py
│   │   ├── delimiters.py
│   │   ├── identifier.py
│   │   ├── state_machine.py
│   │   ├── models.py
│   │   └── loop_maps/
│   │       ├── 837p_loops.json
│   │       ├── 837i_loops.json
│   │       ├── 835_loops.json
│   │       └── 834_loops.json
│   ├── validator/
│   │   ├── __init__.py
│   │   ├── engine.py
│   │   ├── npi.py
│   │   └── rules/
│   │       ├── snip1_integrity.json
│   │       ├── snip2_requirements.json
│   │       └── snip3_balancing.json
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── indexer.py
│   │   ├── retriever.py
│   │   ├── explainer.py
│   │   └── knowledge_docs/
│   ├── reconciliation/
│   │   ├── __init__.py
│   │   └── engine.py
│   ├── delta/
│   │   ├── __init__.py
│   │   └── engine.py
│   └── routes/
│       ├── __init__.py
│       ├── parse.py
│       ├── validate.py
│       ├── ai.py
│       ├── reconcile.py
│       └── delta.py
└── frontend/
    ├── package.json
    ├── vite.config.ts
    ├── tailwind.config.js
    └── src/
        ├── App.tsx
        ├── main.tsx
        ├── index.css
        └── components/
            ├── FileUpload.tsx
            ├── EdiTree.tsx
            ├── ValidationSummary.tsx
            ├── SegmentDetail.tsx
            ├── AiPanel.tsx
            ├── ReconciliationView.tsx
            └── DeltaView.tsx
```

---

## Verification Plan

### Automated Tests (per phase)

#### Phase 1 — Parsing
```bash
cd backend
python -m pytest tests/test_parser.py -v
```
- **`test_delimiter_extraction`**: Assert correct `*`, `:`, `~` from ISA header of each test file.
- **`test_transaction_identification`**: Assert 837P → `CLAIM_837P`, 835 → `REMITTANCE_835`, etc.
- **`test_837p_loop_structure`**: Parse `837P.edi`, assert Loop 2000A (Billing Provider), Loop 2300 (Claim) exist with correct nesting.
- **`test_malformed_837i`**: Parse `837I_malformed.edi`, assert parser completes without crash (graceful degradation).

#### Phase 2 — Validation
```bash
cd backend
python -m pytest tests/test_validator.py -v
```
- **`test_snip1_envelope_balancing`**: Valid file → 0 SNIP-1 errors. Malformed file → envelope mismatch errors.
- **`test_snip2_required_segments`**: Remove a mandatory segment from test data → assert error raised.
- **`test_snip3_claim_balancing`**: Alter `CLM02` to create imbalance beyond $0.01 → assert SNIP-3 error.
- **`test_npi_luhn`**: Valid NPI (`1234567893`) passes Luhn; invalid (`1234567890`) fails.

#### Phase 3 — AI
```bash
cd backend
python -m pytest tests/test_ai.py -v
```
- **`test_phi_masking`**: Assert patient names, DOBs, SSNs are replaced before LLM prompt construction.
- **`test_mmr_retrieval`**: Index a small test corpus, query, assert top-5 results with λ=0.5 produce diverse sources.

#### Phase 4 — Differentiators
```bash
cd backend
python -m pytest tests/test_reconciliation.py tests/test_delta.py -v
```
- **`test_claim_matching`**: 837 with CLM01=`CLAIM001` + 835 with CLP01=`CLAIM001` → matched, amounts compared.
- **`test_834_delta_detection`**: Two 834 files with one added and one terminated member → correct diff output.

### Browser Integration Tests

After each phase, use the browser tool to verify:

1. **Phase 1**: Navigate to `http://localhost:5173`, upload `837P.edi`, confirm JSON response renders (no tree yet — raw JSON display is acceptable).
2. **Phase 2**: Upload `837P.edi`, confirm collapsible tree renders with error badges. Upload `837I_malformed.edi`, confirm validation errors appear in summary.
3. **Phase 3**: Click "Explain" on a validation error, confirm AI panel shows plain-English explanation with sources.
4. **Phase 4**: Upload 837 + 835, confirm reconciliation table. Upload two 834 files, confirm delta view with color-coded rows.

### Manual Verification (User)

> [!IMPORTANT]
> After Phase 2 is complete, please manually verify that:
> 1. The tree view correctly represents the loop hierarchy of the 837P test file.
> 2. Validation errors on the malformed 837I file match your expectations.
> 3. NPI lookups return real provider data from NPPES.

---

## Constraints & Design Decisions

| Decision | Rationale |
|---|---|
| **No message broker** | Hackathon scope — direct FastAPI request/response is sufficient |
| **ChromaDB local mode** | Zero infrastructure overhead, persists to disk, per [.cursorrules](file:///c:/Users/ryan/OneDrive/Desktop/COEP/.cursorrules) |
| **Luhn check before NPPES call** | Fail-fast: ~40% of NPI errors are syntactically invalid; saves network roundtrips |
| **JSON rule files over code** | Adding new validation rules requires zero Python changes — extensible by design |
| **PHI masking in `explainer.py`** | Privacy by Design ([.cursorrules](file:///c:/Users/ryan/OneDrive/Desktop/COEP/.cursorrules) §3) — masking at the call boundary, not in the prompt template |
| **O(n) single-pass parser** | Per user requirement; no backtracking, no DOM construction — stream-friendly |
