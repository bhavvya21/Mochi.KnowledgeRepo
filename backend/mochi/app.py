import hashlib
import secrets
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
import httpx
from fastapi import FastAPI, Request, HTTPException, UploadFile, File, Form
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.concurrency import run_in_threadpool
from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from .config import Settings
from .db import database, Workspace, Session, Document, Chunk, public_document
from .schema import DocumentInput, Query
from .models import LocalModels, Ollama
from .service import RagService
from .ingest import parse_file


class BodyLimit:
    def __init__(self, app, limit):self.app,self.limit=app,limit
    async def __call__(self, scope, receive, send):
        if scope["type"]!="http":return await self.app(scope,receive,send)
        messages=[];size=0
        while True:
            message=await receive()
            if message["type"]=="http.disconnect":return
            size+=len(message.get("body",b""))
            if size>self.limit:
                return await JSONResponse({"error":"Upload exceeds 16 MB"},413)(scope,receive,send)
            messages.append(message)
            if not message.get("more_body"):break
        async def bounded_receive():
            if messages:return messages.pop(0)
            return await receive()
        await self.app(scope,bounded_receive,send)


def create_app(settings=None, models=None, llm=None, warmup=True):
    settings=settings or Settings()
    engine,factory=database(settings.database_url)
    models=models or LocalModels(settings);llm=llm or Ollama(settings)
    service=RagService(factory,settings,models,llm)
    capacity=threading.BoundedSemaphore(2)
    @asynccontextmanager
    async def lifespan(app):
        if warmup:
            await run_in_threadpool(models.load)
            await run_in_threadpool(service.seed)
        yield
        engine.dispose()
    app=FastAPI(title="Mochi Knowledge API",version="3.0.0",lifespan=lifespan)
    app.state.service=service;app.state.factory=factory;app.state.settings=settings
    app.add_middleware(BodyLimit,limit=settings.max_bytes)

    @app.exception_handler(HTTPException)
    async def http_error(request,exc):return JSONResponse({"error":exc.detail},exc.status_code)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request,exc):return JSONResponse({"error":"Invalid request fields or document limits."},422)
    @app.exception_handler(ValueError)
    async def value_error(request,exc):return JSONResponse({"error":str(exc)},400)
    @app.exception_handler(Exception)
    async def server_error(request,exc):return JSONResponse({"error":"The service could not complete this request. Try again."},503)

    def bridge(request):
        credential=request.headers.get("authorization", "")
        return bool(settings.bridge_key and secrets.compare_digest(credential,"Bearer "+settings.bridge_key))

    @app.middleware("http")
    async def protect(request,call_next):
        if request.url.path.startswith("/api/"):
            if not bridge(request):
                if request.headers.get("sec-fetch-site")=="cross-site":return JSONResponse({"error":"Cross-site access denied"},403)
                if request.method not in ("GET","HEAD") and request.headers.get("origin")!=settings.origin:
                    return JSONResponse({"error":"Cross-origin writes denied"},403)
            response=await call_next(request)
            response.headers["Cache-Control"]="private, no-store"
            response.headers["X-Content-Type-Options"]="nosniff"
            return response
        return await call_next(request)

    cookie="__Host-mochi_python" if settings.secure_cookie else "mochi_python_dev"
    def owner(request):
        if bridge(request):
            raw=request.headers.get("x-mochi-owner","")
            if not raw or len(raw)>150:raise HTTPException(401,"Missing workspace")
            identity="bridge:"+raw
            try:
                with factory.begin() as db:
                    if not db.get(Workspace,identity):db.add(Workspace(id=identity))
            except IntegrityError:pass # concurrent first request created it
            return identity
        token=request.cookies.get(cookie,"")
        if len(token)==64:
            with factory() as db:
                session=db.get(Session,hashlib.sha256(token.encode()).hexdigest())
                if session and session.expires>time.time():return session.owner
        raise HTTPException(401,"Workspace session missing or expired. Reload Mochi.")

    def limited(function,*args):
        if not capacity.acquire(blocking=False):raise HTTPException(429,"Mochi is busy. Please retry shortly.")
        try:return function(*args)
        finally:capacity.release()

    def budget(who):
        with factory.begin() as db:
            workspace=db.scalar(select(Workspace).where(Workspace.id==who).with_for_update())
            now=time.time()
            if now-workspace.request_window>=60:
                workspace.request_window=now;workspace.request_count=0
            if workspace.request_count>=30:raise HTTPException(429,"Workspace limit: 30 processing requests per minute")
            workspace.request_count+=1

    @app.get("/api/health")
    def health():return {"status":"ok","version":3,"backend":"fastapi","answerMode":"ollama-rag"}

    @app.get("/api/ready")
    def ready():
        try:
            with factory() as db:db.execute(select(Workspace.id).limit(1))
            response=httpx.get(settings.ollama_url.rstrip("/")+"/api/tags",timeout=5)
            response.raise_for_status()
            names={m["name"] for m in response.json().get("models",[])}
            if settings.ollama_model not in names:raise ValueError("Model missing")
        except Exception:raise HTTPException(503,"Database or Ollama model is not ready")
        return {"status":"ready","model":settings.ollama_model}

    @app.get("/api/session")
    def session(request:Request):
        token=None
        try:workspace=owner(request)
        except HTTPException:
            token=secrets.token_hex(32);workspace=str(uuid.uuid4())
            with factory.begin() as db:
                db.add(Workspace(id=workspace));db.flush()
                db.add(Session(token_hash=hashlib.sha256(token.encode()).hexdigest(),owner=workspace,expires=time.time()+settings.session_days*86400))
        response=JSONResponse({"user":{"kind":"browser","label":"Private browser workspace"},"storage":True,"answerMode":"ollama-rag",
                               "capabilities":{"rawUploads":True,"dense":True,"reranking":True,"semanticChunking":True,"vision":bool(settings.vision_model)},
                               "limits":{"documents":settings.max_documents,"charactersPerDocument":200000,"totalCharacters":settings.max_characters}})
        if token:response.set_cookie(cookie,token,max_age=settings.session_days*86400,httponly=True,secure=settings.secure_cookie,samesite="lax",path="/")
        return response

    @app.get("/api/documents")
    def documents(request:Request):
        who=owner(request)
        with factory() as db:
            docs=db.scalars(select(Document).where(Document.owner==who).order_by(Document.created.desc())).all()
            return {"documents":[public_document(d) for d in docs]}

    @app.post("/api/documents",status_code=201)
    def add_document(request:Request,document:DocumentInput):
        who=owner(request);budget(who)
        return {"document":limited(service.save,who,document)}

    @app.post("/api/upload",status_code=201)
    async def upload(request:Request,file:UploadFile=File(...),collection:str=Form("My uploads")):
        who=owner(request)
        data=await file.read(settings.max_bytes+1)
        budget(who)
        await file.close()
        if len(data)>settings.max_bytes:raise HTTPException(413,"File too large")
        def ingest():
            doc,warnings=parse_file(Path(file.filename or "document").name,data,llm,collection)
            return {"document":service.save(who,doc),"warnings":warnings}
        return await run_in_threadpool(limited,ingest)

    @app.get("/api/documents/{id}")
    def get_document(id:str,request:Request):
        who=owner(request)
        with factory() as db:
            doc=db.scalar(select(Document).where(Document.id==id,Document.owner==who))
            if not doc:raise HTTPException(404,"Document not found")
            return {"document":public_document(doc)}

    @app.delete("/api/documents/{id}")
    def remove_document(id:str,request:Request):
        who=owner(request)
        with factory.begin() as db:
            # Same lock as ingestion ensures quota/deletion consistency.
            db.scalar(select(Workspace).where(Workspace.id==who).with_for_update())
            doc=db.scalar(select(Document).where(Document.id==id,Document.owner==who))
            if not doc:raise HTTPException(404,"Document not found")
            db.execute(delete(Chunk).where(Chunk.document==id,Chunk.owner==who));db.delete(doc)
        return {"deleted":True}

    @app.post("/api/query")
    def query(request:Request,query:Query):
        who=owner(request)
        budget(who)
        if query.mode=="tfidf":query.mode="dense" # legacy frontend preference migration
        return limited(service.query,who,query)

    @app.post("/api/evaluate")
    def benchmark(request:Request,query:Query):
        import json
        from evaluate import evaluate
        who=owner(request);budget(who)
        path=Path(__file__).resolve().parents[2]/"benchmarks"/"questions-180.json"
        questions=json.loads(path.read_text(encoding="utf-8"))
        # UI benchmark measures retrieval only. Generated-answer evaluation is an offline job.
        start=time.perf_counter()
        report=limited(evaluate,service,questions,query.mode,query.strategy,False)
        return {**report,"recall5":report["recallAt5"],"mrr10":report["mrrAt10"],"p95":report["latencyP95Ms"],
                "duration":(time.perf_counter()-start)*1000,"backend":"fastapi"}

    @app.post("/api/migrate")
    def migrate(request:Request,payload:dict):
        if not bridge(request):raise HTTPException(403,"Migration requires the trusted Sites bridge")
        docs=payload.get("documents")
        if not isinstance(docs,list):raise HTTPException(400,"Documents must be a list")
        limited(service.migrate,owner(request),docs)
        return {"migrated":True}

    @app.get("/api/migration-state")
    def migration_state(request:Request):
        if not bridge(request):raise HTTPException(403,"Trusted bridge required")
        who=owner(request)
        with factory() as db:return {"migrated":db.get(Workspace,who).migrated}

    static=Path(__file__).resolve().parents[2]/"build-client"
    if static.exists():app.mount("/",StaticFiles(directory=static,html=True),name="frontend")
    return app
