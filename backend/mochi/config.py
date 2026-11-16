from dataclasses import dataclass, field
import os


@dataclass
class Settings:
    database_url: str = field(default_factory=lambda: os.getenv("DATABASE_URL", "sqlite:///./mochi.db"))
    origin: str = field(default_factory=lambda: os.getenv("PUBLIC_ORIGIN", "http://localhost:8000"))
    bridge_key: str = field(default_factory=lambda: os.getenv("MOCHI_BRIDGE_KEY", ""))
    ollama_url: str = field(default_factory=lambda: os.getenv("OLLAMA_URL", "http://"+os.getenv("OLLAMA_HOSTNAME","localhost")+":11434"))
    ollama_model: str = field(default_factory=lambda: os.getenv("OLLAMA_MODEL", "qwen2.5:3b"))
    vision_model: str = field(default_factory=lambda: os.getenv("OLLAMA_VISION_MODEL", ""))
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    reranker_model: str = "Xenova/ms-marco-MiniLM-L-6-v2"
    cache_dir: str = field(default_factory=lambda: os.getenv("MODEL_CACHE", "/tmp/mochi-models"))
    secure_cookie: bool = field(default_factory=lambda: os.getenv("COOKIE_SECURE", "true").lower() == "true")
    max_bytes: int = 16 * 1024 * 1024
    max_characters: int = 1_000_000
    max_documents: int = 100
    session_days: int = 90

    def __post_init__(self):
        if self.database_url.startswith("postgres://"):
            self.database_url = self.database_url.replace("postgres://", "postgresql+psycopg://", 1)
        elif self.database_url.startswith("postgresql://"):
            self.database_url = self.database_url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.origin = self.origin.rstrip("/")
        if self.bridge_key and len(self.bridge_key) < 32:
            raise ValueError("MOCHI_BRIDGE_KEY must contain at least 32 characters")
