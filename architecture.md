# System Architecture: US Healthcare EDI Parser & AI Validator (Hybrid Model)

## 1. Data Ingestion & Storage Layer
* **Parser**: Python state-machine converts EDI to JSON.
* **Relational DB (PostgreSQL/SQLite)**: Stores structured EDI data (Claims, Services, Members) to enable exact JOINs and mathematical aggregations.
* **Vector DB (ChromaDB)**: Stores embeddings of HIPAA manuals and denial codes for semantic RAG retrieval.

## 2. Validation Engine (Deterministic)
* **SNIP 1-3**: Executed via SQL queries. 
    * *Example*: `SELECT SUM(service_amt) FROM services WHERE claim_id = X` compared against `claim_total`.
* **NPI Service**: Local Luhn check followed by CMS NPPES API call with in-memory caching.

## 3. AI Intelligence Layer (Semantic)
* **RAG Flow**: When a SQL validation fails, the error code is sent to the Vector DB.
* **MMR Retrieval**: Fetches diverse regulatory context (e.g., matching a "Denied" status in SQL with the "CARC 45" definition in Vector).
* **LLM Explainer**: Synthesizes SQL "facts" and Vector "rules" into a plain-English error report.

## 4. Visualization Layer
* **Interactive Tree**: React-based collapsible view of the Loop hierarchy.
* **Differentiators**: 835 Reconciliation (SQL Join) and 834 Delta Engine (SQL Diff).