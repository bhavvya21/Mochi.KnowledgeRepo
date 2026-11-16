import time
import uuid
from sqlalchemy import create_engine, String, Text, Integer, Float, JSON, ForeignKey, select, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.pool import StaticPool
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "rag_workspaces"
    id: Mapped[str] = mapped_column(String(200), primary_key=True)
    migrated: Mapped[bool] = mapped_column(default=False)
    request_window: Mapped[float] = mapped_column(Float,default=0)
    request_count: Mapped[int] = mapped_column(Integer,default=0)


class Session(Base):
    __tablename__ = "rag_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    owner: Mapped[str] = mapped_column(ForeignKey("rag_workspaces.id"), index=True)
    expires: Mapped[float] = mapped_column(Float)


class Document(Base):
    __tablename__ = "rag_documents"
    id: Mapped[str] = mapped_column(String(100), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner: Mapped[str] = mapped_column(ForeignKey("rag_workspaces.id"), index=True)
    name: Mapped[str] = mapped_column(String(240))
    collection: Mapped[str] = mapped_column(String(80))
    type: Mapped[str] = mapped_column(String(20))
    pages: Mapped[list] = mapped_column(JSON)
    chars: Mapped[int] = mapped_column(Integer)
    size: Mapped[float] = mapped_column(Float, default=0)
    created: Mapped[float] = mapped_column(Float, default=time.time)
    fingerprint: Mapped[str] = mapped_column(String(64), default="")


class Chunk(Base):
    __tablename__ = "rag_chunks"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    document: Mapped[str] = mapped_column(ForeignKey("rag_documents.id", ondelete="CASCADE"), index=True)
    owner: Mapped[str] = mapped_column(String(200), index=True)
    strategy: Mapped[str] = mapped_column(String(20), index=True)
    page: Mapped[int] = mapped_column(Integer)
    topic: Mapped[str] = mapped_column(String(300))
    text: Mapped[str] = mapped_column(Text)
    vector: Mapped[list] = mapped_column(Vector(384).with_variant(JSON(), "sqlite"))


def database(url):
    kwargs = {"pool_pre_ping": True}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in url:
            kwargs["poolclass"] = StaticPool
    engine = create_engine(url, **kwargs)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)
    # Exact filtered vector search intentionally avoids ANN recall loss for small workspaces.
    return engine, sessionmaker(engine, expire_on_commit=False)


def public_document(doc):
    return {"id": doc.id, "name": doc.name, "type": doc.type, "collection": doc.collection,
            "pages": doc.pages, "size": doc.size, "uploaded": doc.owner != "samples",
            "cloud": True, "updated": doc.created}
