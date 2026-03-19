"""
Knowledge Base Indexer — seeds ChromaDB with HIPAA reference material.

Indexes:
  - common_denial_codes.json (CARC/RARC definitions)
  - snip_validation_logic.md (SNIP rules)
  - edi_mapping_reference.md (segment/loop mapping)

Reference: knowledge_index_rules.json for embedding model and retrieval config.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import chromadb
from chromadb.config import Settings

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DENIAL_CODES_PATH = _PROJECT_ROOT / "common_denial_codes.json"
_SNIP_LOGIC_PATH = _PROJECT_ROOT / "snip_validation_logic.md"
_EDI_MAPPING_PATH = _PROJECT_ROOT / "edi_mapping_reference.md"
_CHROMA_DIR = Path(__file__).resolve().parent / "chroma_db"

COLLECTION_NAME = "edi_knowledge"


def get_chroma_client() -> chromadb.ClientAPI:
    """Get or create a persistent ChromaDB client."""
    return chromadb.PersistentClient(path=str(_CHROMA_DIR))


def get_collection(client: chromadb.ClientAPI | None = None):
    """Get or create the EDI knowledge collection."""
    if client is None:
        client = get_chroma_client()
    return client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _load_denial_codes() -> list[dict[str, Any]]:
    """Load CARC/RARC definitions from common_denial_codes.json."""
    if not _DENIAL_CODES_PATH.exists():
        return []
    with open(_DENIAL_CODES_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents: list[dict[str, Any]] = []

    for entry in data.get("CARC_definitions", []):
        doc_text = (
            f"CARC {entry['code']}: {entry['title']} — "
            f"{entry['description']} Action: {entry['action']}"
        )
        documents.append({
            "id": f"CARC_{entry['code']}",
            "text": doc_text,
            "metadata": {
                "source": "CARC_RARC",
                "code": entry["code"],
                "code_type": "CARC",
                "title": entry["title"],
            },
        })

    for entry in data.get("RARC_definitions", []):
        doc_text = (
            f"RARC {entry['code']}: {entry['title']} — "
            f"{entry['description']} Action: {entry['action']}"
        )
        documents.append({
            "id": f"RARC_{entry['code']}",
            "text": doc_text,
            "metadata": {
                "source": "CARC_RARC",
                "code": entry["code"],
                "code_type": "RARC",
                "title": entry["title"],
            },
        })

    return documents


def _load_markdown_chunks(filepath: Path, source_name: str) -> list[dict[str, Any]]:
    """Split a markdown file by ## headers into indexable chunks."""
    if not filepath.exists():
        return []
    text = filepath.read_text(encoding="utf-8")
    sections = text.split("\n## ")

    documents: list[dict[str, Any]] = []
    for i, section in enumerate(sections):
        clean = section.strip()
        if not clean:
            continue
        # Extract section title from first line
        lines = clean.split("\n", 1)
        title = lines[0].strip("# ").strip()
        body = lines[1].strip() if len(lines) > 1 else title

        doc_id = f"{source_name}_{i}_{title[:30].replace(' ', '_')}"
        documents.append({
            "id": doc_id,
            "text": clean,
            "metadata": {
                "source": source_name,
                "section": title,
                "chunk_index": i,
            },
        })

    return documents


def index_knowledge_base(force_reindex: bool = False) -> int:
    """
    Index all knowledge assets into ChromaDB.

    Args:
        force_reindex: If True, delete existing collection and re-index.

    Returns:
        Number of documents indexed.
    """
    client = get_chroma_client()

    if force_reindex:
        try:
            client.delete_collection(COLLECTION_NAME)
        except Exception:
            pass

    collection = get_collection(client)

    # Check if already indexed
    if collection.count() > 0 and not force_reindex:
        return collection.count()

    # Gather all documents
    all_docs: list[dict[str, Any]] = []
    all_docs.extend(_load_denial_codes())
    all_docs.extend(_load_markdown_chunks(_SNIP_LOGIC_PATH, "SNIP_Validation"))
    all_docs.extend(_load_markdown_chunks(_EDI_MAPPING_PATH, "EDI_Mapping"))

    if not all_docs:
        return 0

    # Batch add to ChromaDB
    collection.add(
        ids=[d["id"] for d in all_docs],
        documents=[d["text"] for d in all_docs],
        metadatas=[d["metadata"] for d in all_docs],
    )

    return len(all_docs)


# CLI entry point for manual indexing
if __name__ == "__main__":
    count = index_knowledge_base(force_reindex=True)
    print(f"Indexed {count} documents into ChromaDB collection '{COLLECTION_NAME}'")
