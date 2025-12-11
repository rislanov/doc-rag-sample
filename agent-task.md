Реализуй систему согласно техническому заданию в файле [47] technical_specification.md

Приоритет реализации:
1. DocumentStore (postgres_storage.py) с методом search()
   - PostgreSQL connection
   - to_tsvector('russian', text) + to_tsquery полнотекстовый поиск
   - Параметризованные запросы (защита от SQL injection)
   
2. SemanticChunker (chunking.py)
   - Parsing markdown по heading структуре
   - Token-aware semantic splitting (~500 tokens per chunk)
   - Chunk type inference
   
3. FastAPI endpoints (api.py)
   - POST /ingest
   - POST /query
   - GET /client/{client_id}/profile
   
4. ClientQAGenerator (qa_generator.py)
   - Load Mistral-7B-Instruct v0.2 with 4-bit quantization
   - Build prompt from chunks
   - Generate answer + confidence score
   
5. Docker setup
   - docker-compose.yml with PostgreSQL + API
   - Dockerfile with GPU support
   - requirements.txt

Используй примеры из [48] api_examples_testing.md для тестирования.

Полные детали реализации в [47].
Быстрый старт в [40].
