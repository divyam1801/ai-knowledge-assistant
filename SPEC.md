# Personal AI Knowledge Assistant — Project Spec

## Overview

A personal AI-powered knowledge assistant that lets you upload study notes, PDFs, images of handwritten notes, and other documents into an organized folder structure, then query them using natural language. Built as a RAG (Retrieval-Augmented Generation) application.

**Primary user**: A software engineer preparing for technical interviews, studying from multiple sources (Claude chat exports, textbooks, handwritten notes, PDFs), who wants a single place to store and query everything they've learned.

---

## Use Cases (MVP)

### UC1 — Upload files to organized folders
Upload a file (TXT, PDF, MD, image) into a topic-specific folder (e.g., "Core Java", "System Design", "DSA"). The system parses the file, extracts text (with OCR for images), chunks it, generates embeddings, and stores everything. The file becomes queryable immediately after processing.

### UC2 — Folder-scoped queries
Ask a question scoped to a specific folder. Example: "Summarize what I studied in Core Java." The system retrieves chunks only from the specified folder and generates an answer grounded in that content.

### UC3 — Cross-folder semantic search
Ask a question without specifying a folder. Example: "Tell me about plugins in Java." The system searches across all folders, finds the most relevant chunks regardless of where they live, and answers with citations.

### UC4 — Direct chat upload (ephemeral)
Upload a file directly in the chat interface for a quick Q&A session. The file is processed in-memory (not persisted to the knowledge base). A "Save to knowledge base" option lets the user persist it to a folder after the fact.

### UC5 — Summarization
Ask for summaries at different levels:
- "Summarize what I studied today" (filter by upload date)
- "Summarize everything in the System Design folder" (all content in a folder)
- "Summarize this document" (specific document)

For large folders, use hierarchical summarization: summarize each document first, then summarize the summaries.

---

## Tech Stack

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Frontend | Next.js 14+ (App Router), TypeScript, Tailwind CSS, shadcn/ui | Best web UX, massive ecosystem, natural path to React Native for mobile later |
| Backend | Python 3.11+, FastAPI | Async support, dominant in ML/AI ecosystem, WebSocket for streaming |
| Database | PostgreSQL 16 + pgvector extension | Single DB for relational data and vector search, SQL-native similarity queries |
| File storage | Local disk (`/data/uploads/`) | Simple for MVP, easy S3 migration path later |
| Embeddings | Ollama — `nomic-embed-text` (768-dim) | Free, local, good quality for personal-scale RAG |
| LLM | Ollama — `llama3.1:8b` or `mistral` | Free, local, pluggable to swap providers later |
| OCR | Tesseract (via pytesseract) | Free, open-source, handles printed text well |
| Background jobs | Celery + Redis | Async document processing (chunking + embedding shouldn't block the API) |
| Containerization | Docker + Docker Compose | Local dev + deployment consistency |

---

## Data Model

### ERD

```
users
  ├── id (UUID, PK)
  ├── email (unique)
  ├── name
  ├── password_hash
  ├── created_at
  └── updated_at

folders
  ├── id (UUID, PK)
  ├── user_id (FK → users)
  ├── name (e.g., "Core Java")
  ├── description (optional)
  ├── created_at
  └── updated_at

documents
  ├── id (UUID, PK)
  ├── folder_id (FK → folders)
  ├── user_id (FK → users)
  ├── filename (original filename)
  ├── file_path (path on local disk)
  ├── file_type (txt | pdf | md | image)
  ├── file_size_bytes
  ├── status (processing | ready | failed)
  ├── chunk_count (populated after indexing)
  ├── uploaded_at
  └── updated_at

chunks
  ├── id (UUID, PK)
  ├── document_id (FK → documents)
  ├── folder_id (FK → folders, denormalized for fast filtered search)
  ├── user_id (FK → users, denormalized for fast filtered search)
  ├── content (text content of the chunk)
  ├── chunk_index (position within the document, 0-based)
  ├── token_count
  ├── embedding (vector(768), pgvector column)
  ├── metadata (JSONB — page number, section heading, etc.)
  └── created_at

chat_sessions
  ├── id (UUID, PK)
  ├── user_id (FK → users)
  ├── title (auto-generated or user-set)
  ├── folder_id (FK → folders, nullable — null means cross-folder)
  ├── created_at
  └── updated_at

chat_messages
  ├── id (UUID, PK)
  ├── session_id (FK → chat_sessions)
  ├── role (user | assistant)
  ├── content (message text)
  ├── citations (JSONB — array of {chunk_id, document_id, snippet})
  ├── created_at
  └── updated_at
```

### Indexes

```sql
-- Vector similarity search (primary query path)
CREATE INDEX idx_chunks_embedding ON chunks
  USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Folder-scoped search (UC2)
CREATE INDEX idx_chunks_folder ON chunks (folder_id);

-- User-scoped search
CREATE INDEX idx_chunks_user ON chunks (user_id);

-- Document status checks
CREATE INDEX idx_documents_status ON documents (user_id, status);

-- Folder listing
CREATE INDEX idx_folders_user ON folders (user_id);
```

---

## File Storage Layout

```
/data/uploads/
  └── {user_id}/
      └── {folder_id}/
          └── {document_id}_{original_filename}
```

Files are stored with their document ID prepended to avoid naming collisions. The original filename is preserved in the `documents` table for display purposes.

---

## API Design

### Auth
```
POST   /api/auth/register          → Create account
POST   /api/auth/login             → Get JWT token
GET    /api/auth/me                → Get current user
```

### Folders
```
POST   /api/folders                → Create a folder
GET    /api/folders                → List all folders for the user
GET    /api/folders/{id}           → Get folder details + document list
PATCH  /api/folders/{id}           → Rename / update folder
DELETE /api/folders/{id}           → Delete folder + all its documents and chunks
```

### Documents
```
POST   /api/folders/{id}/documents → Upload file to a folder (triggers async indexing)
GET    /api/documents/{id}         → Get document details
GET    /api/documents/{id}/status  → Check indexing status
DELETE /api/documents/{id}         → Delete document + its chunks
```

### Chat
```
POST   /api/chat/sessions                   → Create a new chat session
GET    /api/chat/sessions                   → List chat sessions
GET    /api/chat/sessions/{id}              → Get session with messages
DELETE /api/chat/sessions/{id}              → Delete a session

POST   /api/chat/sessions/{id}/messages     → Send a message (returns streamed response)
       Body: { "content": "...", "folder_id": null | "uuid" }
       - folder_id: if provided, search is scoped to that folder
       - if null, search spans all folders

POST   /api/chat/upload                     → Upload file + ask question (ephemeral)
       Body: multipart { file, question }
       - File is processed in-memory, not persisted
       - Response includes a "save_to_folder" action

POST   /api/chat/upload/save                → Persist an ephemeral upload to a folder
       Body: { "temp_id": "...", "folder_id": "..." }
```

### Search
```
POST   /api/search                 → Semantic search across knowledge base
       Body: { "query": "...", "folder_id": null | "uuid", "limit": 10 }
       Returns: ranked chunks with document metadata
```

---

## Ingestion Pipeline

### Flow

```
File Upload
    │
    ▼
FastAPI receives file → saves to local disk → creates document record (status: processing)
    │
    ▼
Celery task dispatched (async)
    │
    ├─ If image → Tesseract OCR → extract text
    ├─ If PDF   → PyPDF2 / pdfplumber → extract text
    ├─ If TXT/MD → read directly
    │
    ▼
Text Cleaning
    │ (remove excessive whitespace, normalize unicode)
    ▼
Chunking
    │ Strategy: recursive character splitter
    │ Chunk size: ~500 tokens (~2000 chars)
    │ Overlap: 50 tokens (~200 chars)
    │ Preserve paragraph/section boundaries where possible
    ▼
Embedding Generation
    │ Model: Ollama nomic-embed-text (768 dimensions)
    │ Batch: process chunks in batches of 32
    ▼
Store in PostgreSQL
    │ Insert chunks with embeddings into chunks table
    │ Update document status to "ready"
    │ Update document chunk_count
    ▼
Done — document is now queryable
```

### Error Handling
- If any step fails, set document status to "failed" with an error message
- Support retry: user can trigger re-processing of a failed document
- Partial failures: if 90/100 chunks embed but 10 fail, still mark as "ready" but log the failures

---

## RAG Query Pipeline

### Flow

```
User asks a question
    │
    ▼
Embed the query
    │ Same model: Ollama nomic-embed-text
    ▼
Vector similarity search (pgvector)
    │ SELECT content, document_id, chunk_index, metadata,
    │        1 - (embedding <=> query_embedding) AS similarity
    │ FROM chunks
    │ WHERE user_id = $1
    │   AND ($2::uuid IS NULL OR folder_id = $2)  -- optional folder filter
    │ ORDER BY embedding <=> query_embedding
    │ LIMIT 10;
    ▼
Build prompt with retrieved context
    │
    │ SYSTEM: You are a helpful study assistant. Answer the user's question
    │ based ONLY on the provided context. If the context doesn't contain
    │ the answer, say so. Always cite which document your answer comes from.
    │
    │ CONTEXT:
    │ [Document: session-sept-29.txt, Folder: Core Java]
    │ {chunk content}
    │
    │ [Document: java-notes.pdf, Folder: Core Java]
    │ {chunk content}
    │ ...
    │
    │ USER: {user's question}
    ▼
LLM generates response (streamed)
    │ Model: Ollama llama3.1:8b or mistral
    │ Stream tokens back via WebSocket or SSE
    ▼
Save message + citations to chat history
```

### Summarization variant
For "summarize" queries:
1. Fetch ALL chunks from the target scope (folder / document / date range)
2. If total tokens < context window (8K for most models): single-pass summarization
3. If total tokens > context window: hierarchical — summarize per-document first, then summarize summaries
4. Use a dedicated summarization prompt (not the Q&A prompt)

---

## LLM Provider Abstraction

Design the LLM layer as pluggable so Ollama can be swapped for OpenAI/Claude later:

```python
# app/services/llm/base.py
from abc import ABC, abstractmethod
from typing import AsyncIterator

class LLMProvider(ABC):
    @abstractmethod
    async def embed(self, text: str) -> list[float]:
        """Generate embedding vector for a text string."""
        ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for multiple texts."""
        ...

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        context: str,
        stream: bool = True
    ) -> AsyncIterator[str]:
        """Generate a chat response, optionally streaming."""
        ...

    @abstractmethod
    async def summarize(self, text: str) -> str:
        """Generate a summary of the given text."""
        ...


# app/services/llm/ollama.py
class OllamaProvider(LLMProvider):
    def __init__(self, base_url: str = "http://localhost:11434"):
        self.base_url = base_url
        self.embed_model = "nomic-embed-text"
        self.chat_model = "llama3.1:8b"

    async def embed(self, text: str) -> list[float]:
        # POST to /api/embeddings
        ...

    async def chat(self, messages, context, stream=True):
        # POST to /api/chat with streaming
        ...


# app/services/llm/openai.py (future)
class OpenAIProvider(LLMProvider):
    ...
```

Configuration via environment variable:
```env
LLM_PROVIDER=ollama          # or "openai" later
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_EMBED_MODEL=nomic-embed-text
OLLAMA_CHAT_MODEL=llama3.1:8b
```

---

## Project Structure

```
ai-knowledge-assistant/
├── docker-compose.yml
├── .env.example
├── SPEC.md                          # This file
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── pyproject.toml               # Dependencies (poetry or pip)
│   ├── alembic/                     # DB migrations
│   │   └── versions/
│   ├── app/
│   │   ├── main.py                  # FastAPI app entry point
│   │   ├── config.py                # Settings from env vars
│   │   ├── database.py              # SQLAlchemy engine + session
│   │   │
│   │   ├── models/                  # SQLAlchemy ORM models
│   │   │   ├── user.py
│   │   │   ├── folder.py
│   │   │   ├── document.py
│   │   │   ├── chunk.py
│   │   │   └── chat.py
│   │   │
│   │   ├── schemas/                 # Pydantic request/response schemas
│   │   │   ├── user.py
│   │   │   ├── folder.py
│   │   │   ├── document.py
│   │   │   ├── chat.py
│   │   │   └── search.py
│   │   │
│   │   ├── api/                     # Route handlers
│   │   │   ├── auth.py
│   │   │   ├── folders.py
│   │   │   ├── documents.py
│   │   │   ├── chat.py
│   │   │   └── search.py
│   │   │
│   │   ├── services/                # Business logic
│   │   │   ├── ingestion.py         # Chunking, text extraction
│   │   │   ├── search.py            # Vector search + ranking
│   │   │   ├── rag.py               # RAG pipeline (retrieve + generate)
│   │   │   ├── ocr.py               # Tesseract OCR wrapper
│   │   │   └── llm/
│   │   │       ├── base.py          # Abstract LLMProvider
│   │   │       ├── ollama.py        # Ollama implementation
│   │   │       └── factory.py       # Provider factory from config
│   │   │
│   │   ├── tasks/                   # Celery async tasks
│   │   │   └── indexing.py          # Document processing task
│   │   │
│   │   └── utils/
│   │       ├── chunking.py          # Text splitter
│   │       └── text_cleaning.py     # Unicode normalization, whitespace
│   │
│   └── tests/
│       ├── test_ingestion.py
│       ├── test_search.py
│       └── test_rag.py
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   ├── next.config.js
│   │
│   ├── src/
│   │   ├── app/                     # Next.js App Router
│   │   │   ├── layout.tsx
│   │   │   ├── page.tsx             # Landing / dashboard
│   │   │   ├── login/
│   │   │   ├── register/
│   │   │   ├── folders/
│   │   │   │   ├── page.tsx         # Folder list
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx     # Folder detail (document list)
│   │   │   └── chat/
│   │   │       ├── page.tsx         # New chat
│   │   │       └── [id]/
│   │   │           └── page.tsx     # Chat session
│   │   │
│   │   ├── components/
│   │   │   ├── ui/                  # shadcn/ui components
│   │   │   ├── FileUploader.tsx
│   │   │   ├── FolderCard.tsx
│   │   │   ├── DocumentList.tsx
│   │   │   ├── ChatMessage.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   └── CitationBadge.tsx
│   │   │
│   │   ├── lib/
│   │   │   ├── api.ts              # API client (fetch wrappers)
│   │   │   └── auth.ts             # JWT token management
│   │   │
│   │   └── types/
│   │       └── index.ts            # Shared TypeScript types
│   │
│   └── public/
│
└── data/                            # Gitignored, created at runtime
    └── uploads/
```

---

## Docker Compose (Development)

```yaml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: knowledge_assistant
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

  backend:
    build: ./backend
    ports:
      - "8000:8000"
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/knowledge_assistant
      REDIS_URL: redis://redis:6379/0
      LLM_PROVIDER: ollama
      OLLAMA_BASE_URL: http://host.docker.internal:11434
      UPLOAD_DIR: /data/uploads
    volumes:
      - ./backend:/app
      - uploads:/data/uploads
    depends_on:
      - db
      - redis

  celery-worker:
    build: ./backend
    command: celery -A app.tasks worker --loglevel=info
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/knowledge_assistant
      REDIS_URL: redis://redis:6379/0
      OLLAMA_BASE_URL: http://host.docker.internal:11434
      UPLOAD_DIR: /data/uploads
    volumes:
      - uploads:/data/uploads
    depends_on:
      - db
      - redis

  frontend:
    build: ./frontend
    ports:
      - "3000:3000"
    environment:
      NEXT_PUBLIC_API_URL: http://localhost:8000
    volumes:
      - ./frontend:/app
      - /app/node_modules

volumes:
  pgdata:
  uploads:
```

**Note:** Ollama runs on the host machine (not in Docker) since it needs GPU access. The containers reach it via `host.docker.internal:11434`. Install Ollama on your machine and run:
```bash
ollama pull nomic-embed-text
ollama pull llama3.1:8b
```

---

## Build Order (Suggested)

### Phase 1 — Foundation
1. Set up Docker Compose (Postgres + pgvector, Redis)
2. FastAPI project scaffolding with SQLAlchemy + Alembic
3. Database models and migrations
4. Basic auth (register/login with JWT)

### Phase 2 — Ingestion Pipeline
5. File upload endpoint (folders + documents)
6. Text extraction (TXT, PDF, MD)
7. Chunking service
8. Ollama embedding integration
9. Celery task for async ingestion
10. Document status tracking

### Phase 3 — RAG Query
11. Vector similarity search with pgvector
12. RAG pipeline (retrieve + prompt + generate)
13. Streaming responses (SSE or WebSocket)
14. Citation extraction and linking

### Phase 4 — Frontend
15. Next.js project setup with shadcn/ui
16. Auth pages (login/register)
17. Folder management UI
18. File upload with progress and status
19. Chat interface with streaming responses
20. Citation display (click to see source)

### Phase 5 — Polish
21. Summarization (folder-level, document-level)
22. Ephemeral chat upload (UC4)
23. OCR for images (Tesseract integration)
24. Error handling and retry logic
25. Loading states, empty states, error states in UI

---

## Future Enhancements (V2)

- React Native mobile app (iOS + Android)
- Flashcard generation from documents
- Quiz mode — test yourself on uploaded material
- Web clipper — paste a URL and ingest the page
- Voice input for queries
- Export knowledge base as organized Markdown
- Hybrid search (BM25 keyword + semantic vector, fused with RRF)
- Cross-document linking and knowledge graph
- Multiple LLM provider support (OpenAI, Claude) via config
