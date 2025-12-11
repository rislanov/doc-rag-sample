# Техническое задание: Client Portfolio RAG System

## 1. ОБЗОР ПРОЕКТА

### 1.1 Назначение
Система для анализа многостраничных PDF-документов клиентов на русском языке с возможностью:
- Хранения и индексации семантических chunks документов
- Полнотекстового поиска на русском языке через PostgreSQL
- Ответов на произвольные вопросы через LLM (Mistral-7B)
- Построения портретов клиентов на основе документов

### 1.2 Основные параметры
- **Язык документов:** Русский
- **Масштаб:** до 100M документов (~1000 chunks на документ)
- **Архитектура:** Client ID → Multiple PDFs → OCR (markdown) → PostgreSQL chunks → Query + LLM
- **Пользователи:** Backend система, API клиенты
- **Гарантии:** SLA 1-2 сек на query, 150 docs/sec на ingestion

---

## 2. ФУНКЦИОНАЛЬНЫЕ ТРЕБОВАНИЯ

### 2.1 Ingestion Pipeline

**Input:**
```python
{
    "client_id": "CLIENT_001",
    "doc_id": "contract_2024_01",
    "markdown_content": "# Договор поставки\n## Сумма\n5,000,000 рублей"
}
```

**Process:**
1. Semantic chunking markdown по смыслу (~500 tokens per chunk)
   - Сохранение heading структуры (# ## ###)
   - Сохранение контекста (overlap между chunks)
   - Вывод chunk_type (contract, invoice, payment, risk, general)

2. PostgreSQL storage
   - Таблица `documents` (client_id, doc_id, filename, ingested_at)
   - Таблица `chunks` (client_id, doc_id, chunk_id, chunk_index, text, heading, heading_level, chunk_type, tokens, ingested_at)
   - GIN индекс на `to_tsvector('russian', text)` для полнотекстового поиска
   - B-tree индекс на `client_id` для быстрой фильтрации

**Output:**
```python
{
    "status": "success",
    "chunks_ingested": 45,
    "client_id": "CLIENT_001",
    "doc_id": "contract_2024_01"
}
```

**Performance:** 150 docs/sec на одном A100 GPU

---

### 2.2 Query Endpoint (RAG)

**Input:**
```python
POST /query
{
    "client_id": "CLIENT_001",
    "query": "На какую сумму заключено договоров?"
}
```

**Process:**
1. **Full-text search в PostgreSQL (10-50ms)**
   ```sql
   SELECT chunk_id, doc_id, heading, chunk_type, text,
          ts_rank(to_tsvector('russian', text), 
                  to_tsquery('russian', %s)) as rank
   FROM chunks
   WHERE client_id = %s
     AND to_tsvector('russian', text) @@ to_tsquery('russian', %s)
   ORDER BY rank DESC
   LIMIT 10
   ```
   - Фильтр по client_id (индекс)
   - Лемматизация Russian текста (встроена в PostgreSQL)
   - Ранжирование по ts_rank (релевантность)
   - Возврат TOP 10 chunks

2. **LLM generation (Mistral-7B, 4-bit, 500-2000ms)**
   - Построение prompt из TOP 10 chunks
   - Генерация ответа на русском
   - Вычисление confidence (на основе ранга chunks и length ответа)

**Output:**
```python
{
    "answer": "На основе документов клиента, договоры заключены на сумму 15,500,000 рублей...",
    "confidence": 0.91,
    "sources": [
        {
            "chunk_id": "c_1_1",
            "heading": "Договор поставки №123",
            "chunk_type": "contract",
            "doc_id": "contract_2024_01"
        },
        ...
    ]
}
```

**Performance:** 1-2.5 сек total (100-500ms search + 500-2000ms LLM)

---

### 2.3 Client Profile Endpoint (Analytics)

**Input:**
```
GET /client/{client_id}/profile
```

**Output:**
```python
{
    "client_id": "CLIENT_001",
    "total_documents": 10,
    "total_chunks": 287,
    "portfolio": {
        "total_contract_value": 15500000,
        "currency": "RUB",
        "active_contracts": 8,
        "risk_count": 3
    },
    "chunk_type_distribution": {
        "contract": 45,
        "invoice": 120,
        "payment": 89,
        "risk": 15,
        "general": 18
    }
}
```

---

## 3. СИСТЕМНЫЙ ДИЗАЙН

### 3.1 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│  CLIENT (Batch ingestion or API calls)                      │
├─────────────────────────────────────────────────────────────┤
│  ├─ /ingest (POST) - markdown documents                     │
│  └─ /query (POST) - ask questions                           │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│  FastAPI Backend (uvicorn, 4 workers)                       │
├────────────────────────────────────────────────────────────┤
│  ├─ api.py (routes: /ingest, /query, /client/{id}/profile)│
│  ├─ chunking.py (SemanticChunker class)                    │
│  ├─ postgres_storage.py (DocumentStore + search)          │
│  └─ qa_generator.py (ClientQAGenerator, Mistral-7B)        │
└────────────────────┬────────────────────────────────────────┘
                     │
        ┌────────────┴────────────┐
        │                         │
┌───────▼──────────┐   ┌─────────▼──────────┐
│  PostgreSQL 15   │   │  GPU (A100/H100)   │
├──────────────────┤   ├────────────────────┤
│ - documents      │   │ - e5-large-ru      │
│ - chunks         │   │   (embedding only  │
│ - GIN index      │   │    for future)     │
│ - B-tree index   │   │                    │
│ 100-150GB total  │   │ - Mistral-7B-      │
│                  │   │   Instruct (4-bit) │
└──────────────────┘   │ 14GB VRAM          │
                       └────────────────────┘
```

### 3.2 Data Flow (Query path)

```
User: "На какую сумму договоров?"
     │
     ▼
/query endpoint (fastapi)
     │
     ├─1. PostgreSQL full-text search (10-50ms)
     │   ├─ to_tsvector('russian', text) - лемматизация
     │   ├─ to_tsquery('russian', query) - парсинг запроса
     │   ├─ @@ оператор - полнотекстовый поиск
     │   └─ ts_rank - ранжирование
     │
     ├─2. Retrieve TOP 10 chunks
     │   └─ Result: [chunk_1, chunk_2, ..., chunk_10]
     │
     ├─3. Build LLM prompt
     │   ├─ Chunk 1 (rank 0.95): "Сумма договора: 5,000,000"
     │   ├─ Chunk 2 (rank 0.82): "Счет на 3,500,000"
     │   └─ ... + question
     │
     ├─4. Mistral-7B generation (500-2000ms)
     │   └─ Answer: "На основе документов, договоры на сумму 8,500,000"
     │
     └─5. Return response with confidence & sources
         └─ {"answer": "...", "confidence": 0.91, "sources": [...]}
```

---

## 4. ТЕХНИЧЕСКИЕ СПЕЦИФИКАЦИИ

### 4.1 Technology Stack

| Компонент | Решение | Версия | Причина |
|-----------|---------|--------|---------|
| **DB** | PostgreSQL | 15+ | Native Russian FTS, ACID, масштабируемость |
| **Search** | GIN index | - | 10-50ms для 100M chunks, встроена поддержка русского |
| **Backend** | FastAPI | 0.104+ | Async, performance, простота |
| **Driver** | psycopg2-binary | 2.9+ | Стандартный, безопасность, параметризованные запросы |
| **LLM** | Mistral-7B-Instruct | v0.2 | Russian, QA quality, 4-bit quantization |
| **Quantization** | bitsandbytes | 0.41+ | 4-bit, memory efficiency, minimal quality loss |
| **Container** | Docker | 24+ | Reproducibility, deployment |

### 4.2 PostgreSQL Schema

```sql
-- Documents metadata
CREATE TABLE documents (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(50) NOT NULL,
    doc_id VARCHAR(100) NOT NULL,
    filename VARCHAR(255),
    ingested_at TIMESTAMP DEFAULT NOW()
);

-- Chunks (raw text for search)
CREATE TABLE chunks (
    id SERIAL PRIMARY KEY,
    client_id VARCHAR(50) NOT NULL,
    doc_id VARCHAR(100) NOT NULL,
    chunk_id VARCHAR(100) UNIQUE NOT NULL,
    chunk_index INTEGER,
    text TEXT NOT NULL,
    heading VARCHAR(255),
    heading_level INTEGER,
    chunk_type VARCHAR(50),
    tokens INTEGER,
    ingested_at TIMESTAMP DEFAULT NOW()
);

-- Indices
CREATE INDEX idx_chunks_client ON chunks(client_id);
CREATE INDEX idx_chunks_type ON chunks(chunk_type);
CREATE INDEX idx_chunks_doc ON chunks(doc_id);

-- Full-text search index (Russian)
CREATE INDEX idx_chunks_text_gin ON chunks 
    USING GIN(to_tsvector('russian', text));

-- For ranking
CREATE INDEX idx_chunks_heading ON chunks(heading);
```

### 4.3 Class Design

#### DocumentStore (postgres_storage.py)
```python
class DocumentStore:
    """PostgreSQL storage with Russian full-text search"""
    
    def __init__(self, dbname, user, password, host)
    
    def ingest_chunks(self, chunks: List[Dict]) -> None
        """Insert chunks into PostgreSQL"""
    
    def search(self, client_id: str, query: str, limit: int = 10) -> List[Dict]
        """Full-text search (to_tsvector + to_tsquery + ts_rank)"""
    
    def close(self) -> None
        """Close connection"""
```

**search() implementation:**
- SQL with to_tsvector, to_tsquery, @@ operator, ts_rank
- Parameters: (query, client_id, query, limit)
- psycopg2.execute with parameter binding (safe from SQL injection)
- Return: List of dicts with chunk_id, text, rank, heading, etc.

#### SemanticChunker (chunking.py)
```python
class SemanticChunker:
    """Split markdown by semantic boundaries"""
    
    def __init__(self, chunk_size: int = 512, overlap: int = 50)
    
    def chunk_document(self, text: str, client_id: str, doc_id: str) -> List[Dict]
        """
        Parse markdown structure.
        Preserve heading hierarchy.
        Split by token count.
        Return chunks with metadata.
        """
```

**Logic:**
- Parse markdown (regex for `^#{1,6}` headings)
- Track current heading and level
- Split when token_count > chunk_size
- Use overlap for context
- Infer chunk_type from heading and content

#### ClientQAGenerator (qa_generator.py)
```python
class ClientQAGenerator:
    """LLM-based question answering"""
    
    def __init__(self, model_name: str = "mistralai/Mistral-7B-Instruct-v0.2")
        """Load model with 4-bit quantization"""
    
    def answer_question(
        self, 
        query: str, 
        context_chunks: List[Dict], 
        max_length: int = 500
    ) -> Tuple[str, float]
        """Generate answer from chunks, return (answer, confidence)"""
```

**Prompt template:**
```
## Результаты поиска в документах:

### Chunk 1 (relevance {rank})
{text[:500]}

### Chunk 2 (relevance {rank})
{text[:500]}

... (до 5 chunks)

Вопрос: {query}

Ответь на русском языке. Будь конкретен и ссылайся на документы.

Ответ:
```

#### FastAPI Routes (api.py)
```python
@app.post("/ingest")
async def ingest_document(req: IngestionRequest) -> dict
    """
    POST /ingest
    {
        "client_id": "CLIENT_001",
        "doc_id": "contract_2024_01",
        "markdown_content": "# Договор..."
    }
    """

@app.post("/query")
async def answer_question(req: QueryRequest) -> QueryResponse
    """
    POST /query
    {
        "client_id": "CLIENT_001",
        "query": "На какую сумму договоров?"
    }
    Returns: {"answer": "...", "confidence": 0.91, "sources": [...]}
    """

@app.get("/client/{client_id}/profile")
async def get_client_profile(client_id: str) -> dict
    """Get client portfolio summary"""
```

---

## 5. РЕАЛИЗАЦИЯ ДЕТАЛЕЙ

### 5.1 SemanticChunker specifics

```python
# Input: markdown from OCR
text = """
# Договор поставки №123

Дата: 15.01.2024

## Финансовые условия
- Сумма: 5,000,000 рублей
- НДС: 18%

## Риски
- Просрочка платежа штрафуется...
"""

# Processing:
1. Split by lines
2. Detect headings with regex: r'^(#{1,6})\s+(.+)$'
3. When heading found:
   - Save previous chunk if exists
   - Set new current_heading and current_heading_level
4. When token_count > chunk_size:
   - Save chunk with overlap
   - Reset with last line(s) as context
5. Infer chunk_type from heading + content

# Output chunks:
[
    {
        "chunk_id": "doc_0",
        "text": "# Договор поставки №123\n\nДата: 15.01.2024",
        "heading": "Договор поставки №123",
        "heading_level": 1,
        "type": "contract"
    },
    {
        "chunk_id": "doc_1",
        "text": "## Финансовые условия\n- Сумма: 5,000,000 рублей\n- НДС: 18%",
        "heading": "Финансовые условия",
        "heading_level": 2,
        "type": "contract"
    },
    ...
]
```

### 5.2 PostgreSQL Full-Text Search details

```python
# In DocumentStore.search():

sql = """
SELECT 
    chunk_id,
    doc_id,
    heading,
    chunk_type,
    text,
    ts_rank(
        to_tsvector('russian', text),  -- Convert text to vector
        to_tsquery('russian', %s)      -- Convert query to query
    ) as rank
FROM chunks
WHERE client_id = %s                   -- Filter by client (indexed)
  AND to_tsvector('russian', text) @@ to_tsquery('russian', %s)
  -- @@ operator: "matches"
ORDER BY rank DESC, chunk_index ASC
LIMIT %s
"""

# Parameter binding (safe from injection):
cursor.execute(sql, (query, client_id, query, limit))

# PostgreSQL execution:
# 1. to_tsvector('russian', text) - lemmatizes Russian (built-in)
# 2. to_tsquery('russian', query) - parses Russian query (built-in)
# 3. @@ checks if tsvector matches tsquery
# 4. ts_rank computes relevance (0.0-1.0)
# 5. GIN index on tsvector makes this fast (10-50ms for 100M chunks)
```

### 5.3 LLM Generation details

```python
# In ClientQAGenerator.answer_question():

# Build context from chunks
context = "## Результаты поиска в документах:\n"
for i, chunk in enumerate(context_chunks[:5]):
    context += f"\n### Результат {i+1} (релевантность {chunk['rank']:.2f})\n"
    context += chunk['text'][:400] + "...\n"

# Build prompt
prompt = f"""Ты — помощник по анализу клиентских документов.

{context}

Вопрос: {query}

Ответь кратко, на русском языке. Ссылайся на документы. Если информации нет, скажи об этом.

Ответ:"""

# Generate with Mistral-7B (4-bit quantized)
inputs = tokenizer(prompt, return_tensors="pt").to("cuda")

with torch.no_grad():
    outputs = model.generate(
        inputs['input_ids'],
        max_new_tokens=500,
        temperature=0.7,
        top_p=0.9
    )

answer = tokenizer.decode(outputs[0][inputs['input_ids'].shape[1]:], skip_special_tokens=True)

# Compute confidence
confidence = 0.6 + (avg_rank * 0.3) + (has_specific_facts * 0.1)
```

### 5.4 Error Handling & Validation

```python
# api.py error handling:

try:
    chunks = chunker.chunk_document(...)
    store.ingest_chunks(chunks)
except ValueError as e:
    raise HTTPException(400, f"Invalid markdown: {e}")
except psycopg2.DatabaseError as e:
    raise HTTPException(500, f"Database error: {e}")

# Query validation:
if not req.query or len(req.query) < 3:
    raise HTTPException(400, "Query must be at least 3 characters")

if len(context_chunks) == 0:
    return {
        "answer": f"No documents found for query: {req.query}",
        "confidence": 0.0,
        "sources": []
    }
```

---

## 6. PERFORMANCE & SCALABILITY

### 6.1 Benchmarks

```
Ingestion (1 A100):
- SemanticChunker: 1000+ docs/sec
- PostgreSQL insert: 10k+ rows/sec
- Overall: 150 docs/sec (limited by LLM if extracting features)

Query (Mistral-7B 4-bit):
- PostgreSQL search: 50-100ms (avg case)
- LLM generation: 500-2000ms (depending on answer length)
- Total: 1-2.5 seconds

Storage:
- 100M chunks: 100-150GB PostgreSQL
- 1 chunk average size: 1-2KB text
- GIN index: +30-50GB
```

### 6.2 Scaling Strategy for 100M documents

```
Phase 1 (Week 1-2): Single machine setup
- PostgreSQL on single SSD NVMe
- Mistral-7B inference on single GPU
- Batch ingestion: 8 GPUs parallel
- Time: 100M / (8 * 150 docs/sec) = ~1-2 weeks

Phase 2 (Week 3+): Production deployment
- PostgreSQL replication (primary + replica)
- Query load balancing (multiple FastAPI instances)
- Caching layer (Redis) for hot queries
- Monitoring (Prometheus + Grafana)

Phase 3: Optional optimization
- Add OpenSearch for semantic search (if needed)
- Implement query result caching
- Shard by client_id if single DB becomes bottleneck
```

---

## 7. DEPLOYMENT & INFRASTRUCTURE

### 7.1 Docker Compose (local development)

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: client_docs
    ports: ["5432:5432"]
    volumes: [postgres-data:/var/lib/postgresql/data]

  api:
    build: .
    ports: ["8000:8000"]
    environment:
      POSTGRES_HOST: postgres
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    depends_on: [postgres]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

### 7.2 Dockerfile

```dockerfile
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

WORKDIR /app

RUN apt-get update && apt-get install -y python3.10 python3-pip

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 7.3 requirements.txt

```
fastapi==0.104.1
uvicorn==0.24.0
psycopg2-binary==2.9.9
transformers==4.35.2
torch==2.1.1
bitsandbytes==0.41.1
pydantic==2.5.0
python-dotenv==1.0.0
```

---

## 8. API SPECIFICATION

### 8.1 POST /ingest

**Request:**
```json
{
    "client_id": "CLIENT_001",
    "doc_id": "contract_2024_01",
    "markdown_content": "# Договор поставки...\n\n## Сумма\n5,000,000 рублей"
}
```

**Response (200):**
```json
{
    "status": "success",
    "client_id": "CLIENT_001",
    "doc_id": "contract_2024_01",
    "chunks_ingested": 45
}
```

**Response (400):**
```json
{
    "detail": "Invalid markdown content"
}
```

### 8.2 POST /query

**Request:**
```json
{
    "client_id": "CLIENT_001",
    "query": "На какую сумму заключено договоров?"
}
```

**Response (200):**
```json
{
    "answer": "На основе документов клиента, договоры заключены на сумму 15,500,000 рублей...",
    "confidence": 0.91,
    "sources": [
        {
            "chunk_id": "c_1_1",
            "heading": "Договор поставки №123",
            "chunk_type": "contract",
            "doc_id": "contract_2024_01"
        }
    ]
}
```

### 8.3 GET /client/{client_id}/profile

**Response (200):**
```json
{
    "client_id": "CLIENT_001",
    "total_documents": 10,
    "total_chunks": 287,
    "portfolio": {
        "total_contract_value": 15500000,
        "currency": "RUB"
    }
}
```

---

## 9. TESTING STRATEGY

### 9.1 Unit Tests
```python
# test_chunking.py
def test_markdown_parsing():
    chunker = SemanticChunker()
    chunks = chunker.chunk_document("# Test\n## Sub\ntext", "C1", "D1")
    assert len(chunks) > 0
    assert chunks[0]['heading'] == "Test"

# test_search.py
def test_fulltext_search():
    store = DocumentStore()
    # Insert test chunk
    # Search for it
    # Assert ts_rank > 0
```

### 9.2 Integration Tests
```python
# test_e2e.py
def test_ingest_and_query():
    # Ingest markdown
    # Query for it
    # Assert answer returned with confidence > 0
```

### 9.3 Performance Tests
```python
# test_performance.py
def test_search_latency():
    # Search with 1000 chunks in DB
    # Assert latency < 100ms
    
def test_ingestion_throughput():
    # Ingest 1000 documents
    # Assert throughput > 100 docs/sec
```

---

## 10. MONITORING & OBSERVABILITY

### 10.1 Metrics to track
- Ingestion throughput (docs/sec)
- Query latency (p50, p95, p99)
- Search result count per query
- LLM generation time
- Confidence score distribution
- PostgreSQL query time
- Index hit ratio

### 10.2 Logging
```python
import logging

logger = logging.getLogger(__name__)

logger.info(f"Ingested {len(chunks)} chunks for {client_id}/{doc_id}")
logger.info(f"Search returned {len(results)} chunks in {search_time}ms")
logger.error(f"Database error: {e}")
```

---

## 11. FUTURE ENHANCEMENTS

1. **Caching layer (Redis)**
   - Cache popular queries
   - Cache client profiles

2. **OpenSearch integration (optional)**
   - Add dense vector search (if semantic similarity needed)
   - Hybrid search (BM25 + dense)

3. **Entity extraction**
   - Extract structured facts (contracts, amounts, dates)
   - Build knowledge graph

4. **Multi-language support**
   - Support English, German, French
   - Use multilingual embeddings

5. **Analytics dashboard**
   - Client portfolio visualizations
   - Risk scoring and alerts

---

## DELIVERABLES

1. **postgres_storage.py** - DocumentStore with full-text search
2. **chunking.py** - SemanticChunker for markdown
3. **qa_generator.py** - ClientQAGenerator with Mistral-7B
4. **api.py** - FastAPI routes (/ingest, /query, /profile)
5. **docker-compose.yml** - Local development setup
6. **Dockerfile** - Container definition
7. **requirements.txt** - Python dependencies
8. **tests/** - Unit and integration tests
9. **README.md** - Setup and usage guide

---

## CONSTRAINTS & ASSUMPTIONS

**Constraints:**
- PostgreSQL must support Russian (versions 8.0+)
- GPU required for LLM inference (A100/H100 preferred)
- Network latency: <<100ms for PostgreSQL

**Assumptions:**
- Input markdown is well-formed (from OCR system)
- Client IDs are unique and immutable
- Questions are in Russian
- Documents fit in memory after chunking
- No real-time updates (batch ingestion is fine)

---

## SUCCESS CRITERIA

✅ Ingest 150 docs/sec on single A100
✅ Query latency < 2.5 sec (p95)
✅ Full-text search finds relevant chunks consistently
✅ LLM answers are coherent and cite sources
✅ Confidence score correlates with answer quality
✅ PostgreSQL handles 100M chunks without degradation
✅ API is resilient to edge cases (empty results, malformed queries)
