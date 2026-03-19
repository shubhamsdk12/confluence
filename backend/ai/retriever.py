"""
RAG Retriever — MMR-based semantic search over the ChromaDB knowledge base.

Retrieves diverse, relevant context for validation error explanations.

Config from knowledge_index_rules.json:
  - retrieval_strategy: MMR
  - lambda_param: 0.5
  - top_k: 5
"""
from __future__ import annotations

from typing import Any

from ai.indexer import get_collection, index_knowledge_base


def retrieve_context(
    query: str,
    n_results: int = 5,
    filter_metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Retrieve relevant documents from ChromaDB for a given query.

    Uses ChromaDB's built-in similarity search. For MMR-like diversity,
    we request extra candidates and de-duplicate by source.

    Args:
        query: The search query (e.g., error message or code).
        n_results: Number of results to return (top_k=5 per config).
        filter_metadata: Optional ChromaDB where-filter.

    Returns:
        List of dicts with: text, metadata, distance.
    """
    # Ensure knowledge base is indexed
    index_knowledge_base()

    collection = get_collection()

    kwargs: dict[str, Any] = {
        "query_texts": [query],
        "n_results": min(n_results * 2, 20),  # Fetch extra for diversity
    }
    if filter_metadata:
        kwargs["where"] = filter_metadata

    results = collection.query(**kwargs)

    if not results or not results["documents"]:
        return []

    docs = results["documents"][0]
    metadatas = results["metadatas"][0] if results["metadatas"] else [{}] * len(docs)
    distances = results["distances"][0] if results["distances"] else [0.0] * len(docs)

    # MMR-like diversity: prefer unique sources
    seen_sources: set[str] = set()
    diverse_results: list[dict[str, Any]] = []

    for doc, meta, dist in zip(docs, metadatas, distances):
        source = meta.get("source", "unknown")
        # Prioritize diversity: first occurrence of each source gets priority
        priority = 0 if source not in seen_sources else 1
        diverse_results.append({
            "text": doc,
            "metadata": meta,
            "distance": dist,
            "_priority": priority,
        })
        seen_sources.add(source)

    # Sort by priority (diverse first), then by distance (closest first)
    diverse_results.sort(key=lambda x: (x["_priority"], x["distance"]))

    # Return top_k
    final = diverse_results[:n_results]
    for r in final:
        r.pop("_priority", None)

    return final


def retrieve_for_error_code(code: str, code_type: str = "CARC") -> list[dict[str, Any]]:
    """
    Shortcut to retrieve context for a specific CARC/RARC code.
    """
    return retrieve_context(
        query=f"{code_type} {code}",
        filter_metadata={"code_type": code_type},
        n_results=3,
    )
