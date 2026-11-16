"""Page-preserving chunking, real dense retrieval, BM25, RRF and cross-encoding."""
import math
import re
from collections import Counter
import numpy as np
from sqlalchemy import select
from .db import Chunk, Document


def tokens(text):
    return re.findall(r"\w+", text.lower())


def windows(text, size=140, overlap=20):
    words = text.split()
    return [" ".join(words[i:i+size]) for i in range(0, len(words), size-overlap) if words[i:i+size]]


def chunk_pages(pages, strategy, models):
    result = []
    for page in pages:
        raw = page["text"]
        if strategy == "fixed":
            parts = windows(raw, 120, 20)
        elif strategy in ("semantic", "sentence"):
            sentences = [p.strip() for p in re.split(r"(?<=[.!?])\s+|\n\s*\n", raw) if p.strip()]
            sentences = [p for sentence in sentences for p in windows(sentence)]
            vectors = models.embed(sentences) if strategy == "semantic" else None
            parts, group = [], []
            for i, sentence in enumerate(sentences):
                split = group and (sum(len(s.split()) for s in group)+len(sentence.split()) > 140)
                if vectors is not None and i and group:
                    split = split or cosine(vectors[i-1], vectors[i]) < .45
                if split:
                    parts.append(" ".join(group))
                    group = []
                group.append(sentence)
            if group:
                parts.append(" ".join(group))
        else:
            # Preserve short paragraphs/table rows and all page boundaries.
            parts = [p for paragraph in re.split(r"\n\s*\n", raw) for p in windows(paragraph)]
        result.extend({"page": page["page"], "topic": page.get("topic", ""), "text": p} for p in parts if p.strip())
    return result


def cosine(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return float(np.dot(a,b) / (np.linalg.norm(a)*np.linalg.norm(b) or 1))


def bm25_scores(question, texts):
    bags = [Counter(tokens(t)) for t in texts]
    terms = set(tokens(question))
    lengths = [sum(b.values()) for b in bags]
    average = sum(lengths) / max(1, len(bags)) or 1
    df = Counter(t for b in bags for t in b)
    return [sum(math.log(1+(len(bags)-df[t]+.5)/(df[t]+.5))*b[t]*2.2/
                (b[t]+1.2*(.25+.75*lengths[i]/average)) for t in terms if b[t]) for i,b in enumerate(bags)]


def search(db, owner, query, models, queries):
    base = select(Chunk, Document).join(Document, Chunk.document == Document.id).where(
        Chunk.owner == owner, Document.owner == owner, Chunk.strategy == query.strategy)
    if query.collection != "All knowledge":
        base = base.where(Document.collection == query.collection)
    # Workspace quotas bound exact lexical search. No cross-tenant candidates enter fusion.
    rows = db.execute(base).all()
    if not rows:
        return []
    texts = [c.topic + " " + c.text for c,d in rows]
    aggregate, bm_best, dense_best = {}, {}, {}
    vectors = models.embed(queries)
    for question, vector in zip(queries, vectors):
        lexical = bm25_scores(question, texts)
        dense = [cosine(c.vector, vector) for c,d in rows]
        bm_order = sorted(range(len(rows)), key=lambda i: lexical[i], reverse=True)
        if db.bind.dialect.name == "postgresql":
            dense_rows = db.execute(base.order_by(Chunk.vector.cosine_distance(vector)).limit(30)).all()
            ids = {c.id: i for i,(c,d) in enumerate(rows)}
            dense_order = [ids[c.id] for c,d in dense_rows]
        else:
            dense_order = sorted(range(len(rows)), key=lambda i: dense[i], reverse=True)[:30]
        lists = [bm_order[:30], dense_order] if query.mode == "hybrid" else [bm_order[:30]] if query.mode == "bm25" else [dense_order]
        for order in lists:
            for rank, i in enumerate(order, 1):
                if query.mode == "bm25" and lexical[i] <= 0:
                    continue
                aggregate[i] = aggregate.get(i, 0) + 1/(60+rank)
                bm_best[i] = max(bm_best.get(i,0), lexical[i])
                dense_best[i] = max(dense_best.get(i,-1), dense[i])
    candidates = sorted(aggregate, key=aggregate.get, reverse=True)[:30]
    relevance = models.rerank(query.question, [texts[i] for i in candidates])
    selected = sorted(zip(candidates,relevance), key=lambda x:x[1], reverse=True)[:10]
    hits = []
    for i,score in selected:
        # MS MARCO cross-encoder produces logits; this threshold is configurable in future evaluation.
        if score < -4:
            continue
        c,d = rows[i]
        hits.append({"id":c.id,"document":d.id,"name":d.name,"type":d.type,"collection":d.collection,
                     "page":c.page,"topic":c.topic,"text":c.text,"score":float(score),
                     "bm25":bm_best[i],"cosine":dense_best[i],"fusion":aggregate[i]})
    return hits
