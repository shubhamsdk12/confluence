import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for the Healthcare RAG Validator service."""

    # --- LLM Provider ---
    llm_provider: str = "groq"
    groq_api_key: str = ""
    openai_api_key: str = ""

    # --- Neo4j DB ---
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: str = "password"

    # --- Chroma Vector DB ---
    chroma_persist_dir: str = "./chroma_db"
    embedding_model: str = "all-MiniLM-L6-v2"

    # --- PostgreSQL ---
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/intellifix"

    # --- Paths ---
    base_dir: Path = Path(__file__).resolve().parent.parent
    data_dir: Path = base_dir / "data"

    model_config = SettingsConfigDict(
        env_file=(
            str(Path(__file__).resolve().parent.parent / ".env"),
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
        ),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
