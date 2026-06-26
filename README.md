# Healthcare Document Validation System (RAG + Graph)

An intelligent compliance validation system for healthcare claims (EDI X12 837P and JSON claims). The engine utilizes Retrieval-Augmented Generation (RAG) over HIPAA/X12 guidelines (stored in ChromaDB) and relationship/temporal graph query validation (stored in Neo4j) to detect formatting, structural, semantic, and relational errors. It then invokes an LLM to generate plain-English root-cause explanations and actionable fixes.

## Architecture & Flow

```
Claim File Upload (EDI / JSON) 
   → Classifier 
   → Parse to ClaimIR (Extract fields & log structural errors)
   → Insert to Neo4j Claim Graph
   → Run Graph Validation Checks (Duplicate claims, NPI formats, Future dates)
   → Run ChromaDB Semantic Retrieval (Query for rule texts matching detected errors)
   → LLM Generator (Construct prompts containing claim info, rules context, and relationships)
   → Strict JSON report returned to client
```

## Tech Stack
- **FastAPI** + **Uvicorn** (REST API Backend)
- **ChromaDB** (Local Vector DB for Compliance Rules Retrieval)
- **Neo4j** (Graph database for relationship/entity validation)
- **Sentence-Transformers (`all-MiniLM-L6-v2`)** (Local vector embeddings)
- **Groq Llama 3.3** (Primary LLM) or **OpenAI GPT-4o-mini** (Secondary LLM)
- **Pydantic v2** (Model schemas)
- **Docker Compose** (For running Neo4j locally)

---

## Getting Started

### 1. Configure the Environment
Create a `.env` file in the root `rag_validator` directory (based on `.env.example`):
```env
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=password
CHROMA_PERSIST_DIR=./chroma_db
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### 2. Start Neo4j Database
Run Docker Compose in the `rag_validator` directory:
```bash
docker-compose up -d
```
Neo4j browser will be available at `http://localhost:7474` (username: `neo4j`, password: `password`).

### 3. Setup Python Virtual Environment & Dependencies
Create a virtual environment, activate it, and install required libraries:
```bash
python -m venv venv
venv\Scripts\activate  # On Windows
# source venv/bin/activate # On Unix/macOS

pip install -r requirements.txt
```

### 4. Start the Application
Run the Uvicorn dev server:
```bash
uvicorn app.main:app --reload
```
At startup, the service will:
1. Initialize ChromaDB and automatically load and embed the rules from `data/hipaa_rules.txt`.
2. Connect to the Neo4j database (and display a warning if it's offline).
3. Be ready for requests.

Access interactive API docs at `http://localhost:8000/docs`.

---

## API Endpoints

### 1. Health Status check
- **Endpoint**: `GET /health`
- **Response**:
```json
{
  "status": "healthy",
  "neo4j": true,
  "chroma": true,
  "llm_provider": "groq"
}
```

### 2. Claim Validation Ingest
- **Endpoint**: `POST /api/v1/ingest`
- **Payload**: Multipart file upload (`file=@claim.edi` or `file=@claim.json`)
- **Response Schema**:
```json
{
  "status": "error",
  "filename": "sample_claim.edi",
  "claim_id": "CLM001",
  "total_errors": 3,
  "errors": [
    {
      "error_id": "ERR_A1B2C3",
      "error_type": "structural",
      "field": "provider.npi",
      "value": "12345",
      "rule_violated": "NPI (National Provider Identifier) must be a 10-digit numeric string. Invalid NPI causes claim rejection.",
      "regulation_cited": "HIPAA 837P loop 2010AA / NPI standards",
      "explanation": "The NPI value '12345' provided contains only 5 digits. Regulations mandate that the NPI must be exactly 10 digits.",
      "fix_action": "Resubmit the claim with a valid 10-digit National Provider Identifier (NPI) registered in the NPPES database.",
      "severity": "critical"
    }
  ],
  "summary": "3 errors found: 2 critical, 1 warnings. Claim is not ready for transmission."
}
```

---

## Test & Demo

We have included preconfigured demo claims with intentional errors inside the `demo/` folder:
1. `demo/sample_claim.edi` - Synthetic EDI X12 837P claiming file.
2. `demo/sample_claim.json` - JSON claim equivalent.

Both files contain:
1. Invalid 5-digit Billing Provider NPI (structural error)
2. Future-dated service date (temporal validation error)
3. Missing ICD-10 Diagnosis Codes / HI segment (HIPAA rule structural violation)

To submit the demo claims:
**EDI Claim Upload Demo:**
```bash
curl -X POST -F "file=@demo/sample_claim.edi" http://localhost:8000/api/v1/ingest
```

**JSON Claim Upload Demo:**
```bash
curl -X POST -F "file=@demo/sample_claim.json" http://localhost:8000/api/v1/ingest
```
