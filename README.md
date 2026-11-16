# Mochi — hosted private document search

Mochi now has a hosted backend. Its public interface remains at the existing Sites URL; private document operations use an automatically created browser workspace. ChatGPT sign-in is not required. The user chose cited source excerpts until an AI provider is connected.

## Runtime

- React frontend and a Cloudflare Worker API, deployed together through Sites.
- D1 stores document metadata and ownership. R2 stores extracted document pages as JSON.
- A 256-bit random token is stored in a Secure, HttpOnly, SameSite=Lax, host-only cookie. D1 stores only its SHA-256 digest, workspace owner and expiry. SQL scopes every read/delete to that owner. Existing platform-authenticated workspaces remain supported for compatibility; a valid browser workspace takes precedence.
- Original PDFs/images/spreadsheets are parsed on the device. Extracted text, page numbers and metadata are then sent to the backend. Original binaries are not saved online.
- Server-side BM25 + TF-IDF retrieval, three chunking options, exact excerpts and page-level citations. Sample knowledge and private uploads are explicitly separated.
- Document structure chunks are bounded to 140 words with 20-word overlap on long pages. Fixed windows use 24 words with four-word overlap. Sentence chunks are capped to 140 words.
- There is no LLM, dense embedding model, cross-encoder, team sharing or generated synthesis connected.

## Hosted API

| Route | Behavior |
| --- | --- |
| GET /api/session | Initialize or restore a private browser session; return storage availability and limits |
| GET /api/health | Service health and answer mode |
| GET /api/documents | List the current user's saved documents and text |
| POST /api/documents | Validate and save extracted source pages |
| GET /api/documents/:id | Fetch an owned document; other users receive 404 |
| DELETE /api/documents/:id | Remove owned document content and metadata |
| POST /api/query | Search `uploads` (private session) or `samples` (public) |

POST requests require JSON and a same-origin Origin header. Query input has a 2,000-character limit. The server streams request bodies through a bounded reader. Names, formats, page numbers and text size are validated. IDs and object keys are server-generated. Upload failure rolls back its staged R2 object. SQL inserts atomically enforce per-owner storage quotas.

## Limits and boundaries

50 documents and 1,000,000 extracted characters per user; 100,000 characters and 150 nonempty pages per document. The browser accepts original files up to 15 MB. Uploading the same file twice creates two documents. Searches read the user's bounded corpus into memory; this is intended for small personal workspaces, not enterprise-scale corpora. Original image OCR is English-only; scanned PDF pages need separate image uploads. Complex PDF table reconstruction is not implemented. Uploaded text is treated as data and never executed.

There is no organization membership/role system, public document sharing, background ingestion queue, virus scanner, advanced per-user traffic limiter, lifecycle backup UI or independently measured production SLA. For legacy platform-account workspaces, the platform must remain the trusted ingress that strips visitor-supplied identity headers and injects authenticated identity. Do not expose the Worker directly outside that ingress.

R2 and D1 are separate services: deletion removes the object before metadata. A D1 outage after object deletion can leave an unavailable metadata row; retrying deletion removes it. Failed uploads can leave an orphan only if cleanup itself fails. These failure cases should receive reconciliation jobs before larger-scale use.

## Existing demo uploads

Earlier browser-only uploads are not silently transmitted. Use **Import to online workspace** to migrate them. Successful imports are removed from the old local list; unimported documents stay available for retry. A browser workspace is accessible only from the browser profile holding its cookie. The cookie expires 90 days after creation. Clearing cookies or expiration loses access; no account recovery is available. Other people using the same browser profile can access the workspace. Uploads are not automatically deleted when access expires; remove them in the app beforehand. The app asks for confirmation before removing cloud documents.

## Development and deployment

Node 24 is used for tests (the test database uses `node:sqlite`). Run `npm ci`, `npm test`, `npm run build`. `npm run db:generate` generates append-only Drizzle migrations from `db/schema.js`. The build emits the Worker at `dist/server/index.js`, bundles frontend assets into it, and copies hosting metadata and migrations to `dist/.openai/`.

The source manifest identifies the existing Site and binds D1 as `DB` and R2 as `BUCKET`. Sites provisions resources and applies migrations during deployment. Do not change the project ID or rewrite applied migration history. API keys must never be placed in browser storage or code.

## Verification

Backend integration tests use a real in-memory SQLite database with the committed migration and an R2 test double. They cover anonymous denial, persistence, page provenance, cross-user list/read/search/delete isolation, ignored client owner/key fields, same-origin enforcement, sample/private separation, quota enforcement, rollback and missing-storage errors. Retrieval tests cover pricing arithmetic, chunk provenance, no-match behavior and computed metrics.

The 180-question benchmark is a synthetic regression set (60 facts × 3 templates), not an independent enterprise evaluation. Its UI benchmark still runs in the browser against the public sample corpus. Do not treat it as backend end-to-end latency or generated-answer accuracy. No paid model is called; hosting and storage costs are separate.

## Sign-in-free verification

Tests also cover two independent browser sessions, random/expired token rejection, cookie security flags, session restoration, cross-site initialization rejection, and private document isolation. The app offers a fictional Project Bluebird sample document via Add sample document; it is stored as a real private upload in the visitor workspace when clicked.

