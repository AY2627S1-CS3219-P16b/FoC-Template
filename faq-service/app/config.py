"""Configuration shared by the API and the offline indexer."""

import os
from dataclasses import dataclass
from pathlib import Path

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
EMBEDDING_DIMENSIONS = 384
# Includes the encoding procedure, not just the model name. Changing it requires
# rebuilding the complete index so document and query vectors remain compatible.
EMBEDDING_PROFILE = f"{EMBEDDING_MODEL}:fastembed-query-passage-v1"


@dataclass(frozen=True)
class Settings:
    database_url: str
    docs_dir: Path
    model_cache: Path
    local_files_only: bool
    embedding_threads: int
    anthropic_api_key: str
    anthropic_model: str
    anthropic_timeout: float
    min_similarity: float
    requests_per_minute: int
    max_concurrent_requests: int

    @classmethod
    def from_env(cls):
        settings = cls(
            database_url=os.getenv("DATABASE_URL", ""),
            docs_dir=Path(os.getenv("FAQ_DOCS_DIR", str(Path(__file__).resolve().parents[1] / "docs"))),
            model_cache=Path(os.getenv("FAQ_MODEL_CACHE", "/tmp/foc-faq-models")),
            local_files_only=os.getenv("FAQ_MODEL_LOCAL_ONLY", "false").lower() == "true",
            embedding_threads=int(os.getenv("FAQ_EMBEDDING_THREADS", "2")),
            anthropic_api_key=os.getenv("ANTHROPIC_API_KEY", "").strip(),
            anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-haiku-5-5"),
            anthropic_timeout=float(os.getenv("FAQ_ANTHROPIC_TIMEOUT", "25")),
            min_similarity=float(os.getenv("FAQ_MIN_SIMILARITY", "0.65")),
            requests_per_minute=int(os.getenv("FAQ_REQUESTS_PER_MINUTE", "30")),
            max_concurrent_requests=int(os.getenv("FAQ_MAX_CONCURRENT_REQUESTS", "2")),
        )
        if not 0 <= settings.min_similarity <= 1:
            raise ValueError("FAQ_MIN_SIMILARITY must be between 0 and 1.")
        if min(settings.embedding_threads, settings.requests_per_minute, settings.max_concurrent_requests) < 1:
            raise ValueError("FAQ thread, rate and concurrency settings must be positive.")
        if not 0 < settings.anthropic_timeout <= 45:
            raise ValueError("FAQ_ANTHROPIC_TIMEOUT must be between 0 and 45 seconds.")
        return settings
