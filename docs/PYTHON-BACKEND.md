# Python RAG backend and deployment

The Python implementation is in `backend/mochi`. React keeps Mochi's existing design, screenshots, navigation and document library. The Cloudflare Worker remains as a compatibility gateway while the existing site is live; it cannot host FastAPI itself.

## Implemented pipeline

1. Server-side uploads: PDF text and table extraction with pdfplumber, scanned-page rendering with PDFium, English Tesseract OCR, spreadsheet sheets/rows with openpyxl, DOCX text/tables and text/CSV/JSON inputs. Raw files are discarded after extraction.
2. Optional Ollama vision model generates labeled descriptions of image and diagram content. Deployment configurations enable `qwen2.5vl:3b`; descriptions are model-generated evidence and can be wrong. Existing text-only uploads need re-uploading for visual processing.
3. Four page-preserving chunk indexes: fixed overlap, paragraph structure, sentence grouping and embedding-based semantic boundaries.
4. Real 384-dimensional `all-MiniLM-L6-v2` embeddings through FastEmbed's ONNX runtime, stored in PostgreSQL/pgvector. SQLite is a test/development fallback, not the hosted database.
5. BM25 + exact dense cosine retrieval, reciprocal-rank fusion, then a `ms-marco-MiniLM-L-6-v2` cross-encoder. All candidate reads are restricted to the authenticated workspace before ranking.
6. Ollama decomposes longer questions into bounded search queries. Generated claims must cite retrieved passages with exact quotes. A second model pass checks entailment. Invalid citations or unsupported claims are removed; an empty result abstains. This is a mitigation, not a guarantee against hallucination.
7. Source-bound arithmetic supports sum, difference, product and ratio with Decimal. Numeric operands must occur in exact quoted evidence. Operations and units are checked by a model. Complex financial assumptions, compounded formulas and incomplete tables still require human review.
8. Evaluation uses the existing 180 synthetic development questions against the Python retrieval pipeline. The UI measures retrieval; the offline evaluator optionally evaluates generated answers. It does not invent accuracy, citation correctness or hallucination scores.

## Run the full stack

Requirements: Docker Compose, sufficient disk for models, and at least 8 GB available memory for the Ollama service plus the API/database. CPU inference works but may be slow; a compatible GPU server is preferable for latency-sensitive use.

```powershell
Copy-Item .env.example .env
# Set a strong POSTGRES_PASSWORD in .env before starting.
docker compose up --build -d
docker compose logs -f api ollama
```

The original React frontend is served by FastAPI at `http://localhost:8000`. This is a local validation path, not online deployment. `/api/health` is process liveness; `/api/ready` checks database connectivity and the configured Ollama text model. Wait for model pulls before asking questions. Ollama has no published port.

## Online deployment on Render

The root `render.yaml` defines a Docker web service, private Ollama service and PostgreSQL database. It uses paid compute (2 GB API, 8 GB Ollama) and persistent model storage. Review Render's current displayed charges before provisioning. These files do not imply resources have already been created.

1. Connect Render to this GitHub repository and create a Blueprint from `render.yaml`.
2. Set `PUBLIC_ORIGIN` to the API's actual HTTPS origin. Keep `COOKIE_SECURE=true`. Render sets the database connection, private Ollama hostname and generated bridge secret.
3. Wait for both models to download and `/api/ready` to return 200. Run the upload/query/privacy smoke tests against the hosted endpoint before routing existing users there.
4. Keep `MOCHI_BRIDGE_KEY` server-side. Configure the existing Sites project's runtime secrets with that same key and `MOCHI_PYTHON_URL` set to the API HTTPS origin.
5. Publish the updated Worker/frontend through the existing Sites workflow. The existing Mochi URL is retained and API traffic goes to Python. **Do not enable the URL before the Python service passes readiness and functional checks.**

The gateway never forwards caller-supplied identity/authorization headers. It resolves the existing cookie, uses a server secret and sends a server-selected workspace identity to FastAPI. Python namespaces gateway identities separately from new direct-host workspaces. No model API key is needed for private self-hosted Ollama.

## Existing document migration

On first use after cutover, the gateway reads that user's existing D1/R2 documents and imports them into PostgreSQL. A locked workspace flag makes migration idempotent and prevents later re-import from resurrecting documents deleted from Python. IDs are namespaced deterministically per owner; source page numbers are retained. Migration runs before the user's first document listing.

The original D1/R2 records are retained as migration backups; they are not served by Python after migration. They require a separately reviewed retention/purge procedure. Rolling back to the old service can expose its older state and does not include documents created only on Python. Do not promise seamless bidirectional rollback. Old browser sessions remain managed by Sites; clearing/expiring their cookie still loses access.

## Tests and evaluation

```powershell
$env:PYTHONPATH = 'backend'
python -m pip install -r backend/requirements.txt
python -m pytest backend/tests -q
$env:RUN_MODEL_TESTS = '1'
python -m pytest backend/tests/test_models_live.py -q
python backend/evaluate.py --output work/retrieval-report.json
python backend/evaluate.py --generate --output work/answer-report.json
```

Set `DATABASE_URL`, `OLLAMA_URL` and model names for the environment under test. Test doubles are confined to the unit tests. Production never substitutes hash vectors or a fake generator. The opt-in test downloads and runs real neural models. GitHub Actions runs both API tests and the real model smoke test on Linux.

The supplied questions remain a development set. Compare `--mode hybrid|dense|bm25` and `--strategy structure|fixed|sentence|semantic`. Reports include Recall@5, MRR@10, measured p95, exact quote validity and reference-answer containment. Quote validity and string containment are not semantic correctness; review `manualCorrect` and `manualUnsupportedClaims` before reporting answer accuracy or hallucination rate. Use a new held-out corpus for final project claims.

## Operational boundaries

- 100 documents / one million extracted characters per workspace; 200 pages / 200,000 characters per document; 15 MB frontend uploads. Exact per-workspace search is bounded and not validated at enterprise scale.
- Two concurrent processing tasks per API process and 30 processing requests per minute per workspace. New anonymous workspaces can bypass per-workspace quotas; internet-wide abuse protection should be added at ingress for broader public use.
- Ingestion is synchronous, not a durable background queue. Large scanned PDFs or cold CPU models can exceed host/proxy request timeouts. Reduce document size or use a GPU/queue deployment before high-volume use.
- OCR is English-only. Spreadsheet formulas use cached values; Word citations are logical page 1. Difficult tables, merged cells, reading order and diagram descriptions require inspection.
- Guest-cookie permissions isolate workspaces; there is no team RBAC, account recovery or SSO administration UI.
- Initial SQL tables are created at startup. Future schema changes need explicit migrations; never delete production tables to upgrade them.
- Self-hosted Ollama avoids a per-token API bill, not hosting costs. No accuracy or sub-five-second latency target has been demonstrated yet.

## Primary references

- [FastAPI container deployment](https://fastapi.tiangolo.com/deployment/docker/)
- [Ollama structured outputs](https://docs.ollama.com/capabilities/structured-outputs)
- [Ollama vision](https://docs.ollama.com/capabilities/vision)
- [FastEmbed rerankers](https://qdrant.tech/documentation/fastembed/fastembed-rerankers/)
- [pgvector Python integration](https://github.com/pgvector/pgvector-python)
- [Render Blueprint specification](https://render.com/docs/blueprint-spec)
