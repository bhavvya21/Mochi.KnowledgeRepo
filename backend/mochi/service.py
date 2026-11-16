import hashlib
import json
import time
import uuid
from pathlib import Path
from sqlalchemy import select, delete, func
from .db import Workspace, Document, Chunk, public_document
from .retrieval import chunk_pages, search
from .schema import DocumentInput


class RagService:
    def __init__(self, factory, settings, models, llm):
        self.factory,self.settings,self.models,self.llm=factory,settings,models,llm

    def prepared(self, document):
        pages=[p.model_dump() for p in document.pages]
        chunks=[]
        for strategy in ("structure","fixed","sentence","semantic"):
            parts=chunk_pages(pages,strategy,self.models)
            vectors=self.models.embed([p["text"] for p in parts])
            chunks.extend({**p,"strategy":strategy,"vector":v} for p,v in zip(parts,vectors))
        return pages,chunks

    def save(self, owner, document, document_id=None):
        pages,chunks=self.prepared(document)
        with self.factory.begin() as db:
            workspace=db.scalar(select(Workspace).where(Workspace.id==owner).with_for_update())
            if not workspace: raise ValueError("Workspace does not exist")
            count,total=db.execute(select(func.count(Document.id),func.coalesce(func.sum(Document.chars),0)).where(Document.owner==owner)).one()
            chars=sum(len(p["text"]) for p in pages)
            if count>=self.settings.max_documents or total+chars>self.settings.max_characters:
                raise ValueError("Workspace quota exceeded")
            doc=Document(id=document_id or str(uuid.uuid4()),owner=owner,name=document.name,type=document.type,collection=document.collection,pages=pages,chars=chars,size=document.size)
            db.add(doc);db.flush()
            db.add_all(Chunk(document=doc.id,owner=owner,**c) for c in chunks)
            return public_document(doc)

    def migrate(self, owner, documents):
        # Prepare before transaction, then lock workspace and apply exactly once.
        with self.factory() as db:
            workspace=db.get(Workspace,owner)
            if workspace and workspace.migrated:return
        validated=[(d["id"],DocumentInput.model_validate(d)) for d in documents]
        if len(validated)>self.settings.max_documents or sum(sum(len(p.text) for p in d.pages) for _,d in validated)>self.settings.max_characters:
            raise ValueError("Migration exceeds workspace quota")
        prepared=[(id,d,*self.prepared(d)) for id,d in validated]
        with self.factory.begin() as db:
            workspace=db.scalar(select(Workspace).where(Workspace.id==owner).with_for_update())
            if workspace.migrated:return
            for legacy_id,d,pages,chunks in prepared:
                # Namespaced deterministic ID prevents cross-workspace collisions.
                id=str(uuid.uuid5(uuid.NAMESPACE_URL,owner+":"+legacy_id))
                db.add(Document(id=id,owner=owner,name=d.name,type=d.type,collection=d.collection,pages=pages,chars=sum(len(p["text"]) for p in pages),size=d.size))
                db.flush()
                db.add_all(Chunk(document=id,owner=owner,**c) for c in chunks)
            workspace.migrated=True

    def seed(self):
        path=Path(__file__).resolve().parents[2]/"benchmarks"/"corpus.json"
        if not path.exists():return
        with self.factory.begin() as db:
            if not db.get(Workspace,"samples"):db.add(Workspace(id="samples"))
        for d in json.loads(path.read_text(encoding="utf-8")):
            with self.factory() as db:
                exists=db.get(Document,d["id"])
            if not exists:self.save("samples",DocumentInput.model_validate(d),d["id"])

    def query(self, owner, query):
        start=time.perf_counter()
        queries=[query.question];warnings=[]
        if query.decompose and len(query.question.split())>10:
            try:queries=list(dict.fromkeys([query.question]+self.llm.plan(query.question)))[:5]
            except Exception:warnings.append("Query planning unavailable; searched the original question.")
        with self.factory() as db:
            hits=search(db,"samples" if query.scope=="samples" else owner,query,self.models,queries)
        retrieval_ms=(time.perf_counter()-start)*1000
        claims=[];calculations=[];answer_mode="retrieval"
        if query.generate and hits:
            try:
                claims=self.llm.answer(query.question,hits[:6])
                if any(word in query.question.lower() for word in ("cost","total","difference","compar","ratio","sum")):
                    calculations=self.llm.calculations(query.question,hits[:6])
                answer_mode="generated" if claims or calculations else "abstained"
            except Exception:
                claims=[];calculations=[];answer_mode="unavailable"
                warnings.append("Ollama generation is unavailable. Retrieved evidence is shown; no generated answer was produced.")
        elif query.generate:answer_mode="abstained"
        answer="\n\n".join(c["text"]+" "+" ".join(f"[{i}]" for i in sorted({e['source'] for e in c['evidence']})) for c in claims)
        if answer_mode=="abstained":answer="I could not find enough supported evidence to answer this question."
        return {"question":query.question,"hits":hits,"claims":claims,"calculations":calculations,"answer":answer,"answerMode":answer_mode,
                "elapsed":(time.perf_counter()-start)*1000,"retrievalMs":retrieval_ms,"scope":query.scope,
                "collection":query.collection,"mode":query.mode,"strategy":query.strategy,"isComparison":False,
                "trace":{"queries":queries,"embedding":self.settings.embedding_model,"reranker":self.settings.reranker_model,
                         "generator":self.settings.ollama_model,"fusion":"RRF k=60","quoteValidation":True},"warnings":warnings}
