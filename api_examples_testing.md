# API Examples & Testing

## Пример 1: Ingestion

### Request
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "doc_id": "contract_2024_01",
    "markdown_content": "# Договор поставки №123\n\nДата: 15.01.2024\nПартнер: ООО Поставщик\n\n## Финансовые условия\n\nСумма договора: 5,000,000 рублей\nНДС: 18%\nОбщая сумма: 5,900,000 рублей\n\n## Условия платежа\n\n- Авансовый платеж: 30% при подписании\n- Платеж по отгрузке: 70% при получении товара\n\n## Риски\n\n### Просрочки платежей\n\nВ истории отношений выявлены следующие просрочки:\n- Платеж от 01.02.2023: просрочка на 15 дней\n- Платеж от 15.03.2023: просрочка на 7 дней\n- Штраф за просрочку: 0.5% в день от суммы\n\n## Условия доставки\n\nДоставка осуществляется транспортной компанией ООО Логистика.\nСроки доставки: 5-7 рабочих дней после отгрузки."
  }'
```

### Response (Success)
```json
{
  "status": "success",
  "client_id": "CLIENT_001",
  "doc_id": "contract_2024_01",
  "chunks_ingested": 12
}
```

---

## Пример 2: Query - Сумма договора

### Request
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "query": "На какую сумму договор?"
  }'
```

### Response (Success)
```json
{
  "answer": "На основе документов клиента, договор заключен на сумму 5,000,000 рублей. С учетом НДС 18% общая сумма составляет 5,900,000 рублей. Из этой суммы авансовый платеж составляет 30% (1,500,000 рублей), остаток 70% (3,500,000 рублей) подлежит оплате при получении товара.",
  "confidence": 0.94,
  "sources": [
    {
      "chunk_id": "c_0_2",
      "heading": "Финансовые условия",
      "chunk_type": "contract",
      "doc_id": "contract_2024_01"
    },
    {
      "chunk_id": "c_0_3",
      "heading": "Условия платежа",
      "chunk_type": "contract",
      "doc_id": "contract_2024_01"
    }
  ]
}
```

---

## Пример 3: Query - Риски

### Request
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "query": "Есть ли риски с просрочками платежей?"
  }'
```

### Response (Success)
```json
{
  "answer": "Да, выявлены серьезные риски с просрочками платежей. В истории отношений зафиксированы два случая просрочки: платеж от 01.02.2023 на 15 дней и платеж от 15.03.2023 на 7 дней. Предусмотрен штраф за просрочку в размере 0.5% в день от суммы договора. Рекомендуется усилить контроль над сроками платежей.",
  "confidence": 0.91,
  "sources": [
    {
      "chunk_id": "c_0_4",
      "heading": "Риски",
      "chunk_type": "risk",
      "doc_id": "contract_2024_01"
    },
    {
      "chunk_id": "c_0_5",
      "heading": "Просрочки платежей",
      "chunk_type": "risk",
      "doc_id": "contract_2024_01"
    }
  ]
}
```

---

## Пример 4: Query - Условия доставки

### Request
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "query": "Как осуществляется доставка?"
  }'
```

### Response (Success)
```json
{
  "answer": "Доставка осуществляется транспортной компанией ООО Логистика. Сроки доставки составляют 5-7 рабочих дней после отгрузки товара.",
  "confidence": 0.87,
  "sources": [
    {
      "chunk_id": "c_0_6",
      "heading": "Условия доставки",
      "chunk_type": "contract",
      "doc_id": "contract_2024_01"
    }
  ]
}
```

---

## Пример 5: Query - Нет результатов

### Request
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "query": "Какой цвет упаковки?"
  }'
```

### Response (No match)
```json
{
  "answer": "К сожалению, информация о цвете упаковки не найдена в документах клиента.",
  "confidence": 0.15,
  "sources": []
}
```

---

## Пример 6: Client Profile

### Request
```bash
curl http://localhost:8000/client/CLIENT_001/profile
```

### Response (Success)
```json
{
  "client_id": "CLIENT_001",
  "total_documents": 1,
  "total_chunks": 12,
  "portfolio": {
    "total_contract_value": 5900000,
    "currency": "RUB",
    "active_contracts": 1,
    "risk_count": 1,
    "total_payment_history_value": 0
  },
  "chunk_type_distribution": {
    "contract": 8,
    "risk": 2,
    "general": 2
  },
  "documents": [
    {
      "doc_id": "contract_2024_01",
      "filename": "contract_2024_01",
      "chunk_count": 12,
      "ingested_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

---

## Пример 7: Multiple Documents

### Ingestion 1: Contract
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "doc_id": "contract_2024_02",
    "markdown_content": "# Договор поставки №456\n\n## Сумма\n3,500,000 рублей"
  }'
```

### Ingestion 2: Invoice
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "doc_id": "invoice_2024_01",
    "markdown_content": "# Счет-фактура №001\n\n## Сумма счета\n2,100,000 рублей\n\n## НДС\n378,000 рублей"
  }'
```

### Query: Total portfolio
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "query": "На какую общую сумму договоры и счета?"
  }'
```

### Response
```json
{
  "answer": "На основе документов клиента, договоры заключены на общую сумму 8,500,000 рублей (договор №123 на 5,000,000 + договор №456 на 3,500,000). Дополнительно выдано счетов на сумму 2,100,000 рублей. Общая стоимость контрактов и счетов составляет 10,600,000 рублей.",
  "confidence": 0.89,
  "sources": [
    {
      "chunk_id": "c_0_2",
      "heading": "Финансовые условия",
      "chunk_type": "contract",
      "doc_id": "contract_2024_01"
    },
    {
      "chunk_id": "c_1_2",
      "heading": "Сумма",
      "chunk_type": "contract",
      "doc_id": "contract_2024_02"
    },
    {
      "chunk_id": "i_0_1",
      "heading": "Сумма счета",
      "chunk_type": "invoice",
      "doc_id": "invoice_2024_01"
    }
  ]
}
```

---

## Error Cases

### Error 1: Invalid markdown
```bash
curl -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "doc_id": "bad_doc",
    "markdown_content": null
  }'
```

Response:
```json
{
  "detail": "markdown_content must be a non-empty string"
}
```

### Error 2: Query too short
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "query": "?"
  }'
```

Response:
```json
{
  "detail": "Query must be at least 3 characters"
}
```

### Error 3: Client not found
```bash
curl http://localhost:8000/client/NONEXISTENT/profile
```

Response:
```json
{
  "client_id": "NONEXISTENT",
  "total_documents": 0,
  "total_chunks": 0,
  "portfolio": {
    "total_contract_value": 0,
    "currency": "RUB"
  }
}
```

---

## Performance Testing

### Load test: Ingest 100 documents
```bash
#!/bin/bash

for i in {1..100}; do
  curl -X POST http://localhost:8000/ingest \
    -H "Content-Type: application/json" \
    -d "{
      \"client_id\": \"CLIENT_001\",
      \"doc_id\": \"doc_$i\",
      \"markdown_content\": \"# Document $i\n\n## Section\n\nContent for document $i\"
    }" &
done

wait
```

**Expected:** 100 documents ingested in ~10-15 seconds (10 docs/sec with GPU overhead)

### Latency test: Query after ingest
```bash
#!/bin/bash

# Time the query
time curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{
    "client_id": "CLIENT_001",
    "query": "Content document"
  }'
```

**Expected:** 1-2.5 seconds total (10-50ms search + 500-2000ms LLM)

---

## Batch Testing Script (Python)

```python
import requests
import time
import json

BASE_URL = "http://localhost:8000"
CLIENT_ID = "TEST_CLIENT"

# Ingest
print("Ingesting documents...")
start = time.time()

for i in range(10):
    data = {
        "client_id": CLIENT_ID,
        "doc_id": f"doc_{i}",
        "markdown_content": f"""
# Document {i}

## Section 1
Some content here about contract {i}.

## Section 2
Amount: {1000000 * (i+1)} rublestopWord()."
"""
    }
    
    resp = requests.post(f"{BASE_URL}/ingest", json=data)
    print(f"  Doc {i}: {resp.status_code}")

ingest_time = time.time() - start
print(f"Ingestion took {ingest_time:.2f}s ({10/ingest_time:.0f} docs/sec)\n")

# Query
print("Querying...")
queries = [
    "На какую сумму договоры?",
    "Какие секции есть?",
    "Информация о documento 5?"
]

for query in queries:
    start = time.time()
    resp = requests.post(
        f"{BASE_URL}/query",
        json={"client_id": CLIENT_ID, "query": query}
    )
    elapsed = time.time() - start
    
    result = resp.json()
    print(f"Query: {query}")
    print(f"  Time: {elapsed:.2f}s")
    print(f"  Confidence: {result.get('confidence', 0):.2f}")
    print(f"  Sources: {len(result.get('sources', []))}")
    print()

# Profile
print("Getting profile...")
resp = requests.get(f"{BASE_URL}/client/{CLIENT_ID}/profile")
profile = resp.json()

print(f"Total documents: {profile['total_documents']}")
print(f"Total chunks: {profile['total_chunks']}")
print(f"Portfolio value: {profile['portfolio']['total_contract_value']:,} RUB")
```

---

## Testing Checklist

- [ ] Ingest single document
- [ ] Ingest multiple documents
- [ ] Query with exact match
- [ ] Query with partial match
- [ ] Query with no results
- [ ] Get client profile after ingest
- [ ] Handle invalid markdown
- [ ] Handle very long queries
- [ ] Performance: <3s query latency
- [ ] Performance: 100+ docs/sec ingestion
- [ ] Confidence scores between 0-1
- [ ] Sources contain correct chunk_ids
