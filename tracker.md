# AI Knowledge Assistant — Progress Tracker

## Phase 1 — Foundation
- [x] FastAPI project scaffolding with health endpoint
- [x] SQLAlchemy ORM models (User, Folder, Document, Chunk, ChatSession, ChatMessage)
- [x] Pydantic request/response schemas
- [x] API route handlers (auth, folders, documents, chat, search)
- [x] Alembic migrations with initial schema
- [x] Docker Compose (Postgres + pgvector, Redis) + Dockerfile
- [ ] Run migrations and verify auth flow end-to-end (needs Docker/Postgres)

## Phase 2 — Ingestion Pipeline
- [x] Text extraction services (TXT, PDF, MD)
- [x] OCR for images (Tesseract/pytesseract)
- [x] Chunking service (recursive character splitter, ~500 tokens, 50 overlap)
- [x] LLM provider abstraction + Ollama implementation
- [x] Celery async document indexing task
- [x] Document status tracking (processing -> ready/failed)

## Phase 3 — RAG Query
- [x] Vector similarity search with pgvector
- [x] RAG pipeline (retrieve + prompt + generate)
- [x] SSE streaming responses
- [x] Citation extraction and linking

## Phase 4 — Frontend
- [x] Next.js project setup with Tailwind CSS and shadcn/ui theming
- [x] API client, auth token management, TypeScript interfaces
- [x] Sidebar layout (Notion-style, collapsible folders/chats, add folder, add notes)
- [x] Auth pages (login/register) with error handling
- [x] Folder list and folder detail pages
- [x] File upload with drag-and-drop, status badges, delete
- [x] Chat interface with SSE streaming responses
- [x] Citation badges with expandable snippets
- [x] Search page with folder filtering

## Phase 5 — Polish
- [ ] Summarization (folder-level, document-level, date-scoped)
- [ ] Ephemeral chat upload (UC4)
- [ ] Error handling and retry logic
- [ ] Loading states, empty states, error states in UI
