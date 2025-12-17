# DocRAG - Document RAG System

A system for OCR document recognition, semantic chunking, and RAG-based question answering with Russian language support.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Document Processing Pipeline                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐      ┌────────────┐      ┌──────────────────────────────┐  │
│  │   Document  │──────▶│ RabbitMQ   │──────▶│         Recognizer           │  │
│  │   Upload    │      │(ocr.requests)│     │  ┌────────────────────────┐  │  │
│  └─────────────┘      └────────────┘      │  │     MarkItDown         │  │  │
│   PDF/Word/Excel                          │  │ (Word, Excel, PDF)     │  │  │
│   Images/Scans                            │  └───────────┬────────────┘  │  │
│                                           │              │               │  │
│                                           │              ▼ fallback      │  │
│                                           │  ┌────────────────────────┐  │  │
│                                           │  │      EasyOCR           │  │  │
│                                           │  │ (Images, Scans ru/en)  │  │  │
│                                           │  └───────────┬────────────┘  │  │
│                                           │              │               │  │
│                                           │              ▼ low confidence│  │
│                                           │  ┌────────────────────────┐  │  │
│                                           │  │    Vision LLM          │  │  │
│                                           │  │ (MiniCPM-V: tables,    │  │  │
│                                           │  │  handwritten, complex) │  │  │
│                                           │  └───────────┬────────────┘  │  │
│                                           └──────────────┼───────────────┘  │
│                                                          │ Markdown         │
│                       ┌────────────┐      ┌──────────────▼───────────┐      │
│                       │ RabbitMQ   │◀─────│      PostgreSQL          │      │
│                       │(ocr.results)│     │  (documents fulltext)    │      │
│                       └─────┬──────┘      └──────────────────────────┘      │
│                             │                                                │
│                             ▼                                                │
│                   ┌──────────────────────────┐                              │
│                   │    SemanticChunker       │                              │
│                   │  ┌────────────────────┐  │                              │
│                   │  │ Markdown Parsing   │  │                              │
│                   │  │ + Section Headers  │  │                              │
│                   │  │ + Chunk Type       │  │                              │
│                   │  └─────────┬──────────┘  │                              │
│                   │            ▼             │                              │
│                   │  ┌────────────────────┐  │                              │
│                   │  │    Embeddings      │  │                              │
│                   │  │   (enbeddrus)      │  │                              │
│                   │  │   768 dimensions   │  │                              │
│                   │  └────────────────────┘  │                              │
│                   └────────────┬─────────────┘                              │
│                                │                                             │
│                                ▼                                             │
│                   ┌──────────────────────────┐                              │
│                   │      PostgreSQL          │                              │
│                   │  (chunks + pgvector)     │                              │
│                   │  HNSW Index              │                              │
│                   └──────────────────────────┘                              │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                           Query Processing Pipeline                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────┐      ┌──────────────────┐      ┌────────────────────────┐  │
│  │   User      │──────▶│   DocRAG API     │──────▶│     Hybrid Search      │  │
│  │   Query     │      │   (.NET 8)       │      │  ┌──────────────────┐  │  │
│  └─────────────┘      └────────┬─────────┘      │  │ Fulltext (FTS)   │  │  │
│                                │                 │  │ ts_rank_cd       │  │  │
│                                │                 │  └────────┬─────────┘  │  │
│                                │                 │           │            │  │
│                                │                 │  ┌────────▼─────────┐  │  │
│                                │                 │  │ Vector Search    │  │  │
│                                │                 │  │ pgvector cosine  │  │  │
│                                │                 │  └────────┬─────────┘  │  │
│                                │                 │           │            │  │
│                                │                 │  ┌────────▼─────────┐  │  │
│                                │                 │  │   RRF Fusion     │  │  │
│                                │                 │  │ (k=60)           │  │  │
│                                │                 │  └────────┬─────────┘  │  │
│                                │                 └───────────┼────────────┘  │
│                                │                             │               │
│                                │                             ▼ top-20        │
│                                │                 ┌────────────────────────┐  │
│                                │                 │     Reranker           │  │
│                                │                 │  (Cross-Encoder)       │  │
│                                │                 │  BAAI/bge-reranker-m3  │  │
│                                │                 └────────────┬───────────┘  │
│                                │                              │ top-5        │
│                                ▼                              ▼              │
│                       ┌──────────────────┐      ┌────────────────────────┐  │
│                       │     Ollama       │◀─────│     Context            │  │
│                       │  (Mistral 7B)    │      │  + Ranked Chunks       │  │
│                       └────────┬─────────┘      └────────────────────────┘  │
│                                │                                             │
│                                ▼                                             │
│                       ┌──────────────────────────┐                          │
│                       │        Response          │                          │
│                       │  • Answer (generated)    │                          │
│                       │  • Confidence score      │                          │
│                       │  • Source documents      │                          │
│                       │  • Rerank scores         │                          │
│                       └──────────────────────────┘                          │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Services

### 1. Recognizer (Python)
**Smart Document Processing with Multi-level Fallback**

- **Technologies:** Python 3.11, MarkItDown, EasyOCR (ru, en), Ollama Vision, RabbitMQ, PostgreSQL
- **Functions:**
  - Reads document processing requests from RabbitMQ (`ocr.requests`)
  - **Hybrid Processing (Cascading Fallback):**
    1. **MarkItDown** — for digital files (Word, Excel, PDF) preserving structure (tables, headers)
    2. **EasyOCR** — for scans and images with heuristic Markdown reconstruction
    3. **Vision LLM (MiniCPM-V)** — for complex cases: tables in scans, handwritten text, low OCR confidence (<60%)
  - Auto-detection of document type (passport, table, handwritten)
  - Saves Markdown-formatted text to PostgreSQL
  - Publishes events to `ocr.results`

### 2. SemanticChunker (Python)
**Semantic Document Chunking with Embeddings**

- **Technologies:** Python 3.11, tiktoken, Ollama (enbeddrus), PostgreSQL, RabbitMQ, pgvector
- **Functions:**
  - Listens for events from `ocr.results`
  - Splits Markdown document into semantic chunks (~500 tokens)
  - Preserves structure (section headers, levels)
  - Determines chunk type (passport, ndfl, contract, invoice, risk, financial, etc.)
  - **Generates embeddings** via Ollama (`evilfreelancer/enbeddrus` — Russian-optimized model, 768 dims)
  - Saves chunks + vectors to PostgreSQL with HNSW index
  - Publishes events to `chunking.results`

### 3. Reranker (Python)
**Cross-Encoder Re-ranking for Precise Ranking**

- **Technologies:** Python 3.11, FastAPI, sentence-transformers, BAAI/bge-reranker-v2-m3
- **Functions:**
  - HTTP API for re-ranking search results
  - Uses Cross-Encoder model (~560MB) for precise pairwise query-document comparison
  - **10x faster than LLM-based re-ranking** (50-200ms vs 5-10s)
  - Supports 100+ languages including Russian
  - Normalizes scores to 0-1 range
- **Endpoints:**
  - `POST /rerank` — re-rank documents
  - `GET /health` — health check

### 4. DocRAG API (.NET 8)
**REST API for Search and Q&A**

- **Technologies:** ASP.NET Core 8, Entity Framework Core, PostgreSQL, pgvector, Ollama
- **Endpoints:**
  - `POST /api/search` — **hybrid search** (FTS + semantic with RRF fusion)
  - `POST /api/query` — RAG Q&A with LLM (Mistral 7B)
  - `GET /api/health` — service health check
- **Search Algorithm:**
  1. Fulltext Search (PostgreSQL tsvector, ts_rank_cd)
  2. Vector Search (pgvector, cosine similarity)
  3. RRF Fusion (k=60) to combine results
  4. Cross-Encoder Re-ranking (top-20 → top-5)
  5. LLM Generation with context from top chunks

## Models Used

| Model | Purpose | Size | Language |
|-------|---------|------|----------|
| `mistral:7b-instruct` | LLM for Q&A generation | ~4.1GB | Multi |
| `evilfreelancer/enbeddrus` | Embeddings for semantic search | ~300MB | RU-optimized |
| `minicpm-v` | Vision LLM for complex scans | ~3GB | Multi |
| `BAAI/bge-reranker-v2-m3` | Cross-Encoder for re-ranking | ~560MB | 100+ langs |

## Quick Start

### 1. Start All Services

```bash
# Clone and start
cd doc-rag-sample
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f
```

### 2. Wait for Model Loading

```bash
# Check Ollama model download status
docker logs -f docrag-ollama-pull

# Check readiness of all models
curl http://localhost:11434/api/tags

# Check Reranker
curl http://localhost:8001/health
```

### 3. Check API Readiness

```bash
curl http://localhost:8080/api/health
```

## API Examples

### Hybrid Search (FTS + Vector + Rerank)

```bash
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "contract amount",
    "limit": 10
  }'
```

**Response:**
```json
{
  "query": "contract amount",
  "totalResults": 5,
  "results": [
    {
      "chunkId": 1,
      "documentId": 1,
      "filename": "contract.pdf",
      "content": "## Financial Conditions\n\nThe contract amount is 5,000,000 rubles...",
      "sectionHeader": "Financial Conditions",
      "chunkType": "contract",
      "rank": 0.9234,
      "rerankScore": 0.8912
    }
  ],
  "searchMethod": "hybrid_rrf_rerank"
}
```

### RAG Question Answering

```bash
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What is the contract amount?",
    "maxChunks": 5
  }'
```

**Response:**
```json
{
  "answer": "Based on the documents, the contract is concluded for the amount of 5,000,000 rubles. Including 20% VAT, the total amount is 6,000,000 rubles.",
  "confidence": 0.87,
  "sources": [
    {
      "chunkId": 1,
      "heading": "Financial Conditions",
      "chunkType": "contract",
      "documentId": 1,
      "rerankScore": 0.8912
    }
  ],
  "processingTimeMs": 1250
}
```

### Reranker API (Direct)

```bash
curl -X POST http://localhost:8001/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "contract amount",
    "documents": [
      {"id": "1", "content": "Contract for 5 million rubles"},
      {"id": "2", "content": "The weather is nice today"}
    ],
    "top_k": 2
  }'
```

### Send Document for OCR

```bash
# Send message to RabbitMQ (via Management UI or CLI)
# Queue: ocr.requests
# Message:
{
  "document_id": "doc_001",
  "filename": "contract.pdf",
  "file_path": "/data/documents/contract.pdf",
  "mime_type": "application/pdf"
}
```

## Database Structure

### Table `documents`
| Field | Type | Description |
|-------|------|-------------|
| id | SERIAL | Primary key |
| document_id | VARCHAR(255) | Unique document ID |
| filename | VARCHAR(500) | Filename |
| fulltext | TEXT | Markdown text of the document |
| fulltext_vector | TSVECTOR | Index for FTS |
| processing_method | VARCHAR(50) | Processing method (MARKITDOWN, EASYOCR, VISION_LLM) |
| ocr_confidence | FLOAT | OCR confidence (0-1) |
| metadata | JSONB | Metadata |
| created_at | TIMESTAMP | Creation date |

### Table `chunks`
| Field | Type | Description |
|-------|------|-------------|
| id | SERIAL | Primary key |
| document_id | INTEGER | FK to documents |
| chunk_index | INTEGER | Chunk sequence number |
| content | TEXT | Chunk text |
| content_vector | TSVECTOR | Index for FTS |
| embedding | VECTOR(768) | Embedding vector |
| section_header | VARCHAR(500) | Section header |
| heading_level | INTEGER | Header level (1-6) |
| chunk_type | VARCHAR(50) | Type: contract, invoice, risk, financial, passport, general |
| token_count | INTEGER | Token count |
| created_at | TIMESTAMP | Creation date |

**Indexes:**
- `idx_chunks_embedding` — HNSW index on vector (cosine distance)
- `idx_chunks_content_fts` — GIN index on tsvector
- `idx_chunks_document_id` — B-tree for JOIN

## Ports

| Service | Port | Description |
|---------|------|-------------|
| DocRAG API | 8080 | REST API (.NET) |
| Reranker | 8001 | Re-ranking API (Python) |
| PostgreSQL | 5432 | Database + pgvector |
| RabbitMQ | 5672 | AMQP |
| RabbitMQ UI | 15672 | Management UI (guest/guest) |
| Ollama | 11434 | LLM API |

## Development

### Local Run: DocRAG API

```bash
cd doc-rag
dotnet restore
dotnet run
```

### Local Run: Recognizer

```bash
cd recognizer
pip install -r requirements.txt
python main.py
```

### Local Run: SemanticChunker

```bash
cd semantic-chunker
pip install -r requirements.txt
python main.py
```

### Local Run: Reranker

```bash
cd reranker
pip install -r requirements.txt
python main.py
# Or with uvicorn:
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Configuration

### Environment Variables

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `POSTGRES_HOST` | localhost | PostgreSQL Host |
| `POSTGRES_PORT` | 5432 | PostgreSQL Port |
| `POSTGRES_DB` | docrag | DB Name |
| `POSTGRES_USER` | docrag | User |
| `POSTGRES_PASSWORD` | docrag | Password |
| `RABBITMQ_HOST` | localhost | RabbitMQ Host |
| `RABBITMQ_PORT` | 5672 | RabbitMQ Port |
| `OLLAMA_BASE_URL` | http://localhost:11434 | Ollama URL |
| `OLLAMA_MODEL` | mistral:7b-instruct | LLM Model |
| `EMBEDDING_MODEL` | evilfreelancer/enbeddrus | Embedding Model |
| `VISION_MODEL` | minicpm-v | Vision model for scans |
| `USE_VISION_LLM` | true | Enable Vision LLM fallback |
| `VISION_CONFIDENCE_THRESHOLD` | 0.6 | OCR confidence threshold for Vision fallback |
| `RERANKER_MODEL` | BAAI/bge-reranker-v2-m3 | Cross-Encoder Model |
| `RERANKER_ENABLED` | true | Enable re-ranking |
| `CHUNK_SIZE` | 500 | Chunk size in tokens |
| `CHUNK_OVERLAP` | 50 | Chunk overlap |

## Requirements

- Docker 24+
- Docker Compose 2.0+
- **16GB+ RAM** (recommended for all models)
  - Mistral 7B: ~8GB
  - MiniCPM-V: ~3GB
  - Reranker: ~2GB
  - PostgreSQL/RabbitMQ: ~1GB
- GPU optional (accelerates Ollama and EasyOCR)

## Project Structure

```
doc-rag-sample/
├── docker-compose.yml      # Orchestration of all services
├── db/
│   └── init.sql            # DB Schema + pgvector + indexes
├── recognizer/             # OCR Service (Python)
│   ├── main.py
│   ├── document_processor.py  # MarkItDown + EasyOCR + Vision
│   ├── vision_service.py      # Ollama Vision LLM client
│   ├── ocr_service.py         # EasyOCR wrapper
│   └── Dockerfile
├── semantic-chunker/       # Chunking Service (Python)
│   ├── main.py
│   ├── chunker.py
│   └── Dockerfile
├── reranker/               # Re-ranking Service (Python)
│   ├── main.py             # FastAPI + Cross-Encoder
│   └── Dockerfile
└── doc-rag/                # API Service (.NET 8)
    ├── Controllers/
    ├── Services/
    │   ├── SearchService.cs    # Hybrid search + RRF
    │   ├── RerankService.cs    # Cross-Encoder client
    │   └── QaService.cs        # RAG orchestration
    ├── Data/
    └── Dockerfile
```

## License

MIT