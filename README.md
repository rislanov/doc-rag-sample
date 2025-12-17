# DocRAG - Document RAG System

Система для OCR-распознавания документов, семантического разбиения на чанки и RAG-based вопросно-ответной системы с поддержкой русского языка.

## Архитектура

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

## Сервисы

### 1. Recognizer (Python)
**Smart Document Processing с многоуровневым fallback**

- **Технологии:** Python 3.11, MarkItDown, EasyOCR (ru, en), Ollama Vision, RabbitMQ, PostgreSQL
- **Функции:**
  - Читает запросы на обработку документов из RabbitMQ (`ocr.requests`)
  - **Гибридная обработка (каскадный fallback):**
    1. **MarkItDown** — для цифровых файлов (Word, Excel, PDF) с сохранением структуры (таблицы, заголовки)
    2. **EasyOCR** — для сканов и изображений с эвристическим восстановлением Markdown
    3. **Vision LLM (MiniCPM-V)** — для сложных случаев: таблицы в сканах, рукописный текст, низкая уверенность OCR (<60%)
  - Автоопределение типа документа (passport, table, handwritten)
  - Сохраняет Markdown-форматированный текст в PostgreSQL
  - Публикует события в `ocr.results`

### 2. SemanticChunker (Python)
**Semantic Document Chunking с Embeddings**

- **Технологии:** Python 3.11, tiktoken, Ollama (enbeddrus), PostgreSQL, RabbitMQ, pgvector
- **Функции:**
  - Слушает события из `ocr.results`
  - Разбивает Markdown-документ на семантические чанки (~500 токенов)
  - Сохраняет структуру (заголовки секций, уровни)
  - Определяет тип чанка (passport, ndfl, contract, invoice, risk, financial и др.)
  - **Генерирует эмбеддинги** через Ollama (`evilfreelancer/enbeddrus` — русскоязычная модель, 768 dims)
  - Сохраняет чанки + векторы в PostgreSQL с HNSW индексом
  - Публикует события в `chunking.results`

### 3. Reranker (Python)
**Cross-Encoder Re-ranking для точного ранжирования**

- **Технологии:** Python 3.11, FastAPI, sentence-transformers, BAAI/bge-reranker-v2-m3
- **Функции:**
  - HTTP API для re-ranking результатов поиска
  - Использует Cross-Encoder модель (~560MB) для точного попарного сравнения query-document
  - **10x быстрее LLM-based re-ranking** (50-200ms vs 5-10s)
  - Поддержка 100+ языков включая русский
  - Нормализация скоров в диапазон 0-1
- **Эндпоинты:**
  - `POST /rerank` — перераниживание документов
  - `GET /health` — проверка здоровья

### 4. DocRAG API (.NET 8)
**REST API для поиска и Q&A**

- **Технологии:** ASP.NET Core 8, Entity Framework Core, PostgreSQL, pgvector, Ollama
- **Эндпоинты:**
  - `POST /api/search` — **гибридный поиск** (FTS + семантический с RRF fusion)
  - `POST /api/query` — RAG Q&A с LLM (Mistral 7B)
  - `GET /api/health` — проверка здоровья сервиса
- **Алгоритм поиска:**
  1. Fulltext Search (PostgreSQL tsvector, ts_rank_cd)
  2. Vector Search (pgvector, cosine similarity)
  3. RRF Fusion (k=60) для объединения результатов
  4. Cross-Encoder Re-ranking (top-20 → top-5)
  5. LLM Generation с контекстом из топ чанков

## Используемые модели

| Модель | Назначение | Размер | Язык |
|--------|------------|--------|------|
| `mistral:7b-instruct` | LLM для Q&A генерации | ~4.1GB | Multi |
| `evilfreelancer/enbeddrus` | Эмбеддинги для семантического поиска | ~300MB | RU-optimized |
| `minicpm-v` | Vision LLM для сложных сканов | ~3GB | Multi |
| `BAAI/bge-reranker-v2-m3` | Cross-Encoder для re-ranking | ~560MB | 100+ langs |

## Быстрый старт

### 1. Запуск всех сервисов

```bash
# Клонирование и запуск
cd doc-rag-sample
docker-compose up -d

# Проверка статуса
docker-compose ps

# Просмотр логов
docker-compose logs -f
```

### 2. Дождаться загрузки моделей

```bash
# Проверить статус загрузки Ollama моделей
docker logs -f docrag-ollama-pull

# Проверить готовность всех моделей
curl http://localhost:11434/api/tags

# Проверить Reranker
curl http://localhost:8001/health
```

### 3. Проверка готовности API

```bash
curl http://localhost:8080/api/health
```

## API Примеры

### Гибридный поиск (FTS + Vector + Rerank)

```bash
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "сумма договора",
    "limit": 10
  }'
```

**Ответ:**
```json
{
  "query": "сумма договора",
  "totalResults": 5,
  "results": [
    {
      "chunkId": 1,
      "documentId": 1,
      "filename": "contract.pdf",
      "content": "## Финансовые условия\n\nСумма договора составляет 5,000,000 рублей...",
      "sectionHeader": "Финансовые условия",
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
    "query": "На какую сумму заключен договор?",
    "maxChunks": 5
  }'
```

**Ответ:**
```json
{
  "answer": "На основе документов, договор заключен на сумму 5,000,000 рублей. С учетом НДС 20% общая сумма составляет 6,000,000 рублей.",
  "confidence": 0.87,
  "sources": [
    {
      "chunkId": 1,
      "heading": "Финансовые условия",
      "chunkType": "contract",
      "documentId": 1,
      "rerankScore": 0.8912
    }
  ],
  "processingTimeMs": 1250
}
```

### Reranker API (напрямую)

```bash
curl -X POST http://localhost:8001/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "сумма договора",
    "documents": [
      {"id": "1", "content": "Договор на сумму 5 млн рублей"},
      {"id": "2", "content": "Погода сегодня хорошая"}
    ],
    "top_k": 2
  }'
```

### Отправка документа на OCR

```bash
# Отправить сообщение в RabbitMQ (через Management UI или CLI)
# Queue: ocr.requests
# Message:
{
  "document_id": "doc_001",
  "filename": "contract.pdf",
  "file_path": "/data/documents/contract.pdf",
  "mime_type": "application/pdf"
}
```

## Структура БД

### Таблица `documents`
| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL | Primary key |
| document_id | VARCHAR(255) | Уникальный ID документа |
| filename | VARCHAR(500) | Имя файла |
| fulltext | TEXT | Markdown-текст документа |
| fulltext_vector | TSVECTOR | Индекс для FTS |
| processing_method | VARCHAR(50) | Метод обработки (MARKITDOWN, EASYOCR, VISION_LLM) |
| ocr_confidence | FLOAT | Уверенность OCR (0-1) |
| metadata | JSONB | Метаданные |
| created_at | TIMESTAMP | Дата создания |

### Таблица `chunks`
| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL | Primary key |
| document_id | INTEGER | FK на documents |
| chunk_index | INTEGER | Порядковый номер чанка |
| content | TEXT | Текст чанка |
| content_vector | TSVECTOR | Индекс для FTS |
| embedding | VECTOR(768) | Вектор эмбеддинга |
| section_header | VARCHAR(500) | Заголовок раздела |
| heading_level | INTEGER | Уровень заголовка (1-6) |
| chunk_type | VARCHAR(50) | Тип: contract, invoice, risk, financial, passport, general |
| token_count | INTEGER | Количество токенов |
| created_at | TIMESTAMP | Дата создания |

**Индексы:**
- `idx_chunks_embedding` — HNSW индекс на vector (cosine distance)
- `idx_chunks_content_fts` — GIN индекс на tsvector
- `idx_chunks_document_id` — B-tree для JOIN

## Порты

| Сервис | Порт | Описание |
|--------|------|----------|
| DocRAG API | 8080 | REST API (.NET) |
| Reranker | 8001 | Re-ranking API (Python) |
| PostgreSQL | 5432 | База данных + pgvector |
| RabbitMQ | 5672 | AMQP |
| RabbitMQ UI | 15672 | Management UI (guest/guest) |
| Ollama | 11434 | LLM API |

## Разработка

### Локальный запуск DocRAG API

```bash
cd doc-rag
dotnet restore
dotnet run
```

### Локальный запуск Recognizer

```bash
cd recognizer
pip install -r requirements.txt
python main.py
```

### Локальный запуск SemanticChunker

```bash
cd semantic-chunker
pip install -r requirements.txt
python main.py
```

### Локальный запуск Reranker

```bash
cd reranker
pip install -r requirements.txt
python main.py
# Или с uvicorn:
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Конфигурация

### Переменные окружения

| Переменная | Значение по умолчанию | Описание |
|------------|----------------------|----------|
| `POSTGRES_HOST` | localhost | Хост PostgreSQL |
| `POSTGRES_PORT` | 5432 | Порт PostgreSQL |
| `POSTGRES_DB` | docrag | Имя БД |
| `POSTGRES_USER` | docrag | Пользователь |
| `POSTGRES_PASSWORD` | docrag | Пароль |
| `RABBITMQ_HOST` | localhost | Хост RabbitMQ |
| `RABBITMQ_PORT` | 5672 | Порт RabbitMQ |
| `OLLAMA_BASE_URL` | http://localhost:11434 | URL Ollama |
| `OLLAMA_MODEL` | mistral:7b-instruct | Модель LLM |
| `EMBEDDING_MODEL` | evilfreelancer/enbeddrus | Модель эмбеддингов |
| `VISION_MODEL` | minicpm-v | Vision модель для сканов |
| `USE_VISION_LLM` | true | Включить Vision LLM fallback |
| `VISION_CONFIDENCE_THRESHOLD` | 0.6 | Порог уверенности OCR для Vision fallback |
| `RERANKER_MODEL` | BAAI/bge-reranker-v2-m3 | Модель Cross-Encoder |
| `RERANKER_ENABLED` | true | Включить re-ranking |
| `CHUNK_SIZE` | 500 | Размер чанка в токенах |
| `CHUNK_OVERLAP` | 50 | Перекрытие чанков |

## Требования

- Docker 24+
- Docker Compose 2.0+
- **16GB+ RAM** (рекомендуется для всех моделей)
  - Mistral 7B: ~8GB
  - MiniCPM-V: ~3GB
  - Reranker: ~2GB
  - PostgreSQL/RabbitMQ: ~1GB
- GPU опционально (ускорит Ollama и EasyOCR)

## Структура проекта

```
doc-rag-sample/
├── docker-compose.yml      # Оркестрация всех сервисов
├── db/
│   └── init.sql            # Схема БД + pgvector + индексы
├── recognizer/             # OCR сервис (Python)
│   ├── main.py
│   ├── document_processor.py  # MarkItDown + EasyOCR + Vision
│   ├── vision_service.py      # Ollama Vision LLM client
│   ├── ocr_service.py         # EasyOCR wrapper
│   └── Dockerfile
├── semantic-chunker/       # Chunking сервис (Python)
│   ├── main.py
│   ├── chunker.py
│   └── Dockerfile
├── reranker/               # Re-ranking сервис (Python)
│   ├── main.py             # FastAPI + Cross-Encoder
│   └── Dockerfile
└── doc-rag/                # API сервис (.NET 8)
    ├── Controllers/
    ├── Services/
    │   ├── SearchService.cs    # Hybrid search + RRF
    │   ├── RerankService.cs    # Cross-Encoder client
    │   └── QaService.cs        # RAG orchestration
    ├── Data/
    └── Dockerfile
```

## Лицензия

MIT
