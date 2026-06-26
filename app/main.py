from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.utils.logger import pipeline_logger
from app.knowledge.graph_store import graph_store
from app.knowledge.seed_neo4j import seed_neo4j_database
from app.db.postgres import engine
from app.db.postgres_models import Base

# Import new routers
from app.routes.ingest import router as ingest_router
from app.routes.health import router as health_router
from app.routes.jobs import router as jobs_router
from app.routes.triage import router as triage_router
from app.routes.audit import router as audit_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    pipeline_logger.info("Initializing Phase 2 Enterprise Compliance Platform...")

    # 1. Initialize PostgreSQL tables
    pipeline_logger.info("Creating PostgreSQL database tables...")
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        pipeline_logger.info("PostgreSQL database tables created successfully.")
    except Exception as e:
        pipeline_logger.error(f"Failed to create PostgreSQL database tables: {e}")

    # 2. Connect Neo4j driver and seed compliance rules
    try:
        connected = graph_store.connect()
        if connected:
            pipeline_logger.info("Seeding Neo4j native vector index rules...")
            seed_neo4j_database()
        else:
            pipeline_logger.warning("Neo4j database is offline. Seeding skipped.")
    except Exception as e:
        pipeline_logger.warning(
            f"Failed to connect or seed Neo4j database during startup: {e}"
        )

    pipeline_logger.info(
        f"Compliance Validator ready. LLM Provider: {settings.llm_provider.upper()}"
    )

    yield

    # Shutdown logic
    pipeline_logger.info("Shutting down service...")
    try:
        graph_store.close()
    except Exception as e:
        pipeline_logger.error(f"Error closing Neo4j connection: {e}")


app = FastAPI(
    title="IntelliFix AI — Compliance Platform",
    description="Enterprise Compliance Intelligence & Triage Backend (PostgreSQL + Neo4j GraphRAG).",
    version="2.0.0",
    lifespan=lifespan,
)

# Enable CORS for React frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify the exact domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routes
app.include_router(ingest_router, prefix="/api/v1", tags=["Validation Ingest"])
app.include_router(jobs_router, prefix="/api/v1", tags=["Job Operations"])
app.include_router(triage_router, prefix="/api/v1", tags=["Human-in-the-Loop Triage"])
app.include_router(audit_router, prefix="/api/v1", tags=["Audit & Certification"])
app.include_router(health_router, tags=["Health Checks"])
