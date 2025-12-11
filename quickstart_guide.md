# QUICK START GUIDE: Client Portfolio RAG System

## Что ты передаешь ИИ агенту

Передай файл `technical_specification.md` (47) вместе с этим файлом.

Скажи:
> "Реализуй систему согласно техническому заданию. Начни с этого приоритета:
> 1. DocumentStore класс с методом search() (PostgreSQL + полнотекстовый поиск)
> 2. SemanticChunker для разбивки markdown на chunks
> 3. FastAPI endpoints (/ingest, /query)
> 4. ClientQAGenerator с Mistral-7B
> 5. Docker setup для локальной разработки"

---

## Архитектура в 2 минуты

```
User Question
    ↓
POST /query {"client_id": "C1", "query": "На какую сумму договоров?"}
    ↓
PostgreSQL Full-Text Search (to_tsvector + to_tsquery + ts_rank)
    ↓ Returns: TOP 10 chunks with highest relevance
    ↓
Build LLM Prompt from chunks
    ↓
Mistral-7B Generate Answer (4-bit quantized, ~1.5sec)
    ↓
Return {"answer": "...", "confidence": 0.91, "sources": [...]}
```

---

## 4 главных компонента

### 1. DocumentStore (postgres_storage.py)
```python
store = DocumentStore()

# Вставить chunks
store.ingest_chunks([
    {
        "client_id": "C1",
        "doc_id": "contract_1",
        "chunk_id": "c_1_0",
        "text": "# Договор...",
        "heading": "Договор",
        "chunk_type": "contract"
    }
])

# Полнотекстовый поиск
chunks = store.search("C1", "сумма договора", limit=10)
# SELECT ... WHERE to_tsvector('russian', text) @@ to_tsquery('russian', %s)
# Returns: [{"chunk_id": "...", "text": "...", "rank": 0.95}]
```

### 2. SemanticChunker (chunking.py)
```python
chunker = SemanticChunker(chunk_size=512, overlap=50)

chunks = chunker.chunk_document(
    markdown_content="# Договор\n## Сумма\n5,000,000 рублей",
    client_id="C1",
    doc_id="contract_1"
)
# Returns: [
#   {"chunk_id": "c_1_0", "text": "# Договор", "heading": "Договор"},
#   {"chunk_id": "c_1_1", "text": "## Сумма...", "heading": "Сумма"}
# ]
```

### 3. ClientQAGenerator (qa_generator.py)
```python
qa_gen = ClientQAGenerator(model_name="mistralai/Mistral-7B-Instruct-v0.2")

answer, confidence = qa_gen.answer_question(
    query="На какую сумму договоров?",
    context_chunks=[
        {"text": "Сумма договора: 5,000,000", "rank": 0.95},
        {"text": "Сумма счета: 3,500,000", "rank": 0.82}
    ]
)
# Returns: ("На основе документов, договоры на сумму 8,500,000", 0.91)
```

### 4. FastAPI Routes (api.py)
```python
# POST /ingest
# {"client_id": "C1", "doc_id": "contract_1", "markdown_content": "# ..."}
# → chunks from SemanticChunker
# → store.ingest_chunks()

# POST /query
# {"client_id": "C1", "query": "На какую сумму договоров?"}
# → store.search()
# → qa_gen.answer_question()
# → return {"answer": "...", "confidence": 0.91}
```

---

## Deployment (Docker)

```bash
# Local development
docker-compose up

# API будет на http://localhost:8000
# PostgreSQL на localhost:5432

# Production
docker build -t client-rag:latest .
docker run --gpus all -p 8000:8000 client-rag:latest
```

---

## Key Implementation Details

### PostgreSQL Full-Text Search
```sql
SELECT ... FROM chunks
WHERE client_id = %s
  AND to_tsvector('russian', text) @@ to_tsquery('russian', %s)
ORDER BY ts_rank(...) DESC
LIMIT 10
```
**Что происходит:**
- `to_tsvector('russian', text)` = разбирает русский текст на слова + лемматизирует
- `to_tsquery('russian', query)` = парсит запрос
- `@@` = проверяет совпадение
- `ts_rank()` = вычисляет релевантность (0.0-1.0)
- GIN индекс = быстро (10-50ms на 100M chunks)
- Parameter binding = защита от SQL injection

### SemanticChunking
```python
def chunk_document(self, text: str, client_id: str, doc_id: str):
    chunks = []
    current_heading = None
    current_text = ""
    
    for line in text.split('\n'):
        # Detect heading: r'^(#{1,6})\s+(.+)$'
        if heading_match:
            current_heading = heading_match.group(2)
            current_heading_level = len(heading_match.group(1))
        
        # When text too long
        if token_count(current_text) > chunk_size:
            # Save chunk with overlap
            chunks.append({
                "text": current_text,
                "heading": current_heading,
                "chunk_type": infer_type(current_heading, current_text)
            })
            current_text = overlap_lines  # Keep context
    
    return chunks
```

### LLM Generation
```python
prompt = f"""## Результаты поиска в документах:

### Результат 1 (релевантность 0.95)
Сумма договора: 5,000,000 рублей

### Результат 2 (релевантность 0.82)
Сумма счета: 3,500,000 рублей

Вопрос: На какую сумму договоров?

Ответ:"""

# Mistral-7B generates: "На основе документов, договоры на сумму 8,500,000 рублей"

# Confidence calculation:
confidence = 0.6 + (avg_rank * 0.3) + (has_facts * 0.1)
```

---

## Performance Targets

| Метрика | Целевое значение |
|---------|-----------------|
| **Query latency (p95)** | < 2.5 sec |
| **Search latency** | 10-50 ms |
| **LLM generation** | 500-2000 ms |
| **Ingestion throughput** | 150 docs/sec (A100) |
| **PostgreSQL size for 100M chunks** | 100-150 GB |
| **GIN index size** | +30-50 GB |

---

## Testing Checklist

- [ ] `test_markdown_parsing()` - chunks preserve heading hierarchy
- [ ] `test_fulltext_search()` - rank > 0 for relevant documents
- [ ] `test_sql_injection()` - parameterized queries are safe
- [ ] `test_query_empty_results()` - handle no matches gracefully
- [ ] `test_lm_generation()` - mistral returns coherent answer
- [ ] `test_ingest_throughput()` - 150+ docs/sec
- [ ] `test_search_latency()` - p95 < 100ms

---

## Common Issues & Fixes

**Issue:** `to_tsvector('russian', text)` doesn't work
- **Fix:** PostgreSQL 8.0+ required, verify with `SELECT to_tsvector('russian', 'тест')`

**Issue:** GIN index slow to build on 100M chunks
- **Fix:** Build index in background: `CREATE INDEX CONCURRENTLY ...`

**Issue:** Mistral-7B OOM with 4-bit quantization
- **Fix:** Reduce batch size or use 8-bit quantization instead

**Issue:** Searches return unrelated results
- **Fix:** Reduce chunk_size (more specific chunks) or add chunk_type filter

---

## Files to Generate

The AI agent should create:

1. **postgres_storage.py**
   - `DocumentStore` class
   - `search()` with `to_tsvector` + `to_tsquery`
   - `ingest_chunks()` 
   - Connection pooling (optional)

2. **chunking.py**
   - `SemanticChunker` class
   - Markdown parsing with heading detection
   - Token-aware splitting
   - Overlap handling

3. **qa_generator.py**
   - `ClientQAGenerator` class
   - Load Mistral-7B with 4-bit quantization
   - Prompt building from chunks
   - Confidence calculation

4. **api.py**
   - FastAPI app
   - POST /ingest
   - POST /query
   - GET /client/{client_id}/profile
   - Error handling

5. **models.py**
   - Pydantic models for requests/responses
   - IngestionRequest, QueryRequest, QueryResponse

6. **docker-compose.yml**
   - PostgreSQL service
   - API service with GPU support

7. **Dockerfile**
   - Build from nvidia/cuda:12.2.0-runtime
   - Install Python + dependencies
   - Expose port 8000

8. **requirements.txt**
   - fastapi, uvicorn
   - psycopg2-binary
   - transformers, torch, bitsandbytes
   - pydantic, python-dotenv

9. **tests/test_chunking.py**
   - Unit tests for SemanticChunker

10. **tests/test_storage.py**
    - Unit tests for DocumentStore + search

11. **tests/test_api.py**
    - Integration tests for endpoints

12. **README.md**
    - Setup instructions
    - API documentation
    - Example usage

---

## How to Use After Deployment

```bash
# 1. Ingest documents
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "doc_id": "contract_2024_01",
    "markdown_content": "# Договор поставки №123\n## Сумма\n5,000,000 рублей"
  }'

# 2. Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "query": "На какую сумму договоров?"
  }'

# 3. Get profile
curl http://localhost:8000/client/CLIENT_001/profile
```

---

## Architecture Summary

```
┌─────────────────────────────────────┐
│  FastAPI Backend (4 workers)        │
│  ├─ api.py (routes)                 │
│  ├─ chunking.py (SemanticChunker)   │
│  ├─ postgres_storage.py (search)    │
│  └─ qa_generator.py (Mistral-7B)    │
└────────────┬────────────────────────┘
             │
    ┌────────┴──────────┐
    │                   │
┌───▼────────────┐  ┌──▼────────────┐
│  PostgreSQL 15 │  │  GPU A100/H100 │
│  100-150GB     │  │  Mistral-7B    │
│  GIN index     │  │  4-bit quant   │
│  (for search)  │  │  14GB VRAM     │
└────────────────┘  └────────────────┘
```

**That's it!** Передай это техническое задание ИИ агенту и он реализует систему.
