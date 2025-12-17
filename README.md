# DocRAG - Document RAG System

Система для OCR-распознавания документов, семантического разбиения на чанки и RAG-based вопросно-ответной системы.

## Архитектура

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Document Processing                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐      ┌────────────┐      ┌──────────────────┐      │
│  │   Document  │──────▶│ RabbitMQ   │──────▶│   Recognizer     │      │
│  │   Upload    │      │ (requests) │      │ (MarkItDown+OCR) │      │
│  └─────────────┘      └────────────┘      └────────┬─────────┘      │
│   PDF/Word/Excel                                   │                │
│   Images/Scans                                     │ Markdown       │
│                                                     ▼                │
│                       ┌────────────┐      ┌──────────────────┐      │
│                       │ RabbitMQ   │◀─────│   PostgreSQL     │      │
│                       │ (results)  │      │   (fulltext)     │      │
│                       └─────┬──────┘      └──────────────────┘      │
│                             │                                        │
│                             ▼                                        │
│                       ┌──────────────────┐                          │
│                       │ SemanticChunker  │                          │
│                       │   (Python)       │                          │
│                       └────────┬─────────┘                          │
│                                │ + Embeddings (enbeddrus)           │
│                                ▼                                     │
│                       ┌──────────────────┐                          │
│                       │   PostgreSQL     │                          │
│                       │ (chunks+vectors) │                          │
│                       └──────────────────┘                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         Query Processing                             │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────┐      ┌──────────────────┐      ┌──────────────┐    │
│  │   User      │──────▶│   DocRAG API     │──────▶│  PostgreSQL  │    │
│  │   Query     │      │   (.NET 8)       │      │ Hybrid Search│    │
│  └─────────────┘      └────────┬─────────┘      │ FTS + Vector │    │
│                                │                 └──────────────┘    │
│                                ▼                                     │
│                       ┌──────────────────┐                          │
│                       │     Ollama       │                          │
│                       │  (Mistral 7B)    │                          │
│                       └────────┬─────────┘                          │
│                                │                                     │
│                                ▼                                     │
│                       ┌──────────────────┐                          │
│                       │     Answer       │                          │
│                       │  + Confidence    │                          │
│                       │  + Sources       │                          │
│                       └──────────────────┘                          │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

## Сервисы

### 1. Recognizer (Python)
- **Технологии:** Python 3.11, MarkItDown, EasyOCR (ru, en), RabbitMQ, PostgreSQL
- **Функции:**
  - Читает запросы на обработку документов из RabbitMQ
  - **Гибридная обработка:**
    - MarkItDown — для цифровых файлов (Word, Excel, PDF) с сохранением структуры
    - EasyOCR — для сканов и изображений с эвристическим восстановлением Markdown
  - Сохраняет Markdown-форматированный текст в PostgreSQL
  - Публикует события об успешной обработке

### 2. SemanticChunker (Python)
- **Технологии:** Python 3.11, tiktoken, Ollama (enbeddrus), PostgreSQL, RabbitMQ, pgvector
- **Функции:**
  - Слушает события обработки документов из RabbitMQ
  - Разбивает Markdown-документ на семантические чанки (~500 токенов)
  - Сохраняет структуру (заголовки секций)
  - Определяет тип чанка (passport, ndfl, contract, invoice, risk, financial и др.)
  - **Генерирует эмбеддинги** через Ollama (enbeddrus)
  - Сохраняет чанки + векторы в PostgreSQL (pgvector)

### 3. DocRAG API (.NET 8)
- **Технологии:** ASP.NET Core 8, Entity Framework Core, PostgreSQL, pgvector, Ollama
- **Эндпоинты:**
  - `POST /api/search` - **гибридный поиск** (FTS + семантический)
  - `POST /api/query` - RAG Q&A с LLM (Mistral 7B)
  - `GET /api/health` - проверка здоровья сервиса
- **Поиск:** Reciprocal Rank Fusion (RRF) для объединения результатов FTS и векторного поиска

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

### 2. Дождаться загрузки модели Mistral

```bash
# Проверить статус загрузки
docker logs docrag-ollama-pull

# Или проверить напрямую
curl http://localhost:11434/api/tags
```

### 3. Применение миграций (опционально)

```bash
# Если БД не создалась автоматически
docker exec -it docrag-postgres psql -U docrag -d docrag -f /docker-entrypoint-initdb.d/init.sql
```

## API Примеры

### Полнотекстовый поиск

```bash
curl -X POST http://localhost:8080/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "query": "сумма договора",
    "clientId": "CLIENT_001",
    "limit": 10
  }'
```

**Ответ:**
```json
{
  "query": "сумма договора",
  "totalResults": 2,
  "results": [
    {
      "id": 1,
      "documentId": "doc_001",
      "clientId": "CLIENT_001",
      "filename": "contract.pdf",
      "snippet": "...<b>сумма</b> <b>договора</b> составляет 5,000,000 рублей...",
      "rank": 0.85
    }
  ]
}
```

### RAG Question Answering

```bash
curl -X POST http://localhost:8080/api/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "На какую сумму заключен договор?",
    "clientId": "CLIENT_001",
    "maxChunks": 5
  }'
```

**Ответ:**
```json
{
  "answer": "На основе документов клиента, договор заключен на сумму 5,000,000 рублей. С учетом НДС 18% общая сумма составляет 5,900,000 рублей.",
  "confidence": 0.87,
  "sources": [
    {
      "chunkId": "c_doc_001_2",
      "heading": "Финансовые условия",
      "chunkType": "contract",
      "documentId": "doc_001",
      "rank": 0.92
    }
  ]
}
```

### Отправка документа на OCR

```bash
# Отправить сообщение в RabbitMQ
# Формат сообщения:
{
  "document_id": "doc_001",
  "client_id": "CLIENT_001",
  "filename": "contract.pdf",
  "image_data": "<base64-encoded-image>",
  "page_number": 1
}
```

## Структура БД

### Таблица `documents`
| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL | Primary key |
| document_id | VARCHAR(255) | Уникальный ID документа |
| client_id | VARCHAR(255) | ID клиента |
| filename | VARCHAR(500) | Имя файла |
| fulltext | TEXT | OCR-текст документа |
| metadata | JSONB | Метаданные (OCR детали и т.д.) |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

### Таблица `chunks`
| Поле | Тип | Описание |
|------|-----|----------|
| id | SERIAL | Primary key |
| chunk_id | VARCHAR(255) | Уникальный ID чанка |
| document_id | VARCHAR(255) | ID документа |
| client_id | VARCHAR(255) | ID клиента |
| chunk_index | INTEGER | Порядковый номер чанка |
| text | TEXT | Текст чанка |
| heading | VARCHAR(500) | Заголовок раздела |
| heading_level | INTEGER | Уровень заголовка (1-6) |
| chunk_type | VARCHAR(50) | Тип: contract, invoice, risk, financial, general |
| token_count | INTEGER | Количество токенов |
| created_at | TIMESTAMP | Дата создания |
| updated_at | TIMESTAMP | Дата обновления |

## Порты

| Сервис | Порт | Описание |
|--------|------|----------|
| DocRAG API | 8080 | REST API |
| PostgreSQL | 5432 | База данных |
| RabbitMQ | 5672 | AMQP |
| RabbitMQ UI | 15672 | Management UI |
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

## Конфигурация

### Переменные окружения

| Переменная | Значение по умолчанию | Описание |
|------------|----------------------|----------|
| POSTGRES_HOST | localhost | Хост PostgreSQL |
| POSTGRES_PORT | 5432 | Порт PostgreSQL |
| POSTGRES_DB | docrag | Имя БД |
| POSTGRES_USER | docrag | Пользователь |
| POSTGRES_PASSWORD | docrag | Пароль |
| RABBITMQ_HOST | localhost | Хост RabbitMQ |
| RABBITMQ_PORT | 5672 | Порт RabbitMQ |
| OLLAMA_BASE_URL | http://localhost:11434 | URL Ollama |
| OLLAMA_MODEL | mistral:7b-instruct | Модель LLM |
| CHUNK_SIZE | 500 | Размер чанка в токенах |
| CHUNK_OVERLAP | 50 | Перекрытие чанков |

## Требования

- Docker 24+
- Docker Compose 2.0+
- 8GB+ RAM (для Mistral 7B)
- GPU рекомендуется для OCR и LLM

## Лицензия

MIT
