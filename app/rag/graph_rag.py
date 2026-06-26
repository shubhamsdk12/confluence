from sentence_transformers import SentenceTransformer
from app.config import settings
from app.knowledge.graph_store import graph_store
from app.utils.logger import rag_logger

_model = None

def get_embedding_model() -> SentenceTransformer:
    global _model
    if _model is None:
        rag_logger.info(f"Loading embedding model: {settings.embedding_model}")
        _model = SentenceTransformer(settings.embedding_model)
    return _model

def graphrag_retrieve(error_description: str) -> dict:
    """Retrieve compliance rules, regulations, and historical fixes from Neo4j GraphRAG."""
    rag_logger.info(f"GraphRAG retrieval for: '{error_description}'")
    try:
        model = get_embedding_model()
        embedding = model.encode(error_description).tolist()
    except Exception as e:
        rag_logger.error(f"Failed to generate embedding for query: {e}")
        return {"rules": [], "regulations": [], "historical_fixes": []}

    # 1. Query Neo4j vector index
    rules = graph_store.query_vector_index(embedding, top_k=3)
    
    regulations = []
    historical_fixes = []
    
    # 2. Traverse connections for each rule
    for rule in rules:
        relations = graph_store.get_rule_relations(rule["rule_id"])
        
        for reg in relations["regulations"]:
            if reg not in regulations:
                regulations.append(reg)
                
        for fix in relations["historical_fixes"]:
            fix["rule_id"] = rule["rule_id"]
            fix["rule_name"] = rule["name"]
            historical_fixes.append(fix)

    rag_logger.info(
        f"GraphRAG found {len(rules)} rules, {len(regulations)} regulations, and {len(historical_fixes)} historical fixes."
    )
    
    return {
        "rules": rules,
        "regulations": regulations,
        "historical_fixes": historical_fixes
    }
