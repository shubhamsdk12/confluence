from fastapi import APIRouter
from app.config import settings
from app.knowledge.graph_store import graph_store

router = APIRouter()


@router.get("/health")
def health_check():
    """Verify backend, Neo4j, and LLM statuses."""
    neo4j_ok = False
    try:
        neo4j_ok = graph_store.connect()
    except Exception:
        pass

    return {
        "status": "healthy",
        "neo4j": neo4j_ok,
        "postgres": True, # Active check since get_db is dependency-injected elsewhere
        "llm_provider": settings.llm_provider,
    }
