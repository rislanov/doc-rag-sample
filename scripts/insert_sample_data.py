#!/usr/bin/env python3
"""
Test script to insert sample data directly into PostgreSQL.
Useful for testing search and query without OCR.
"""

import psycopg2
from psycopg2.extras import Json
import uuid
from datetime import datetime

# Database connection
POSTGRES_HOST = "localhost"
POSTGRES_PORT = 5432
POSTGRES_DB = "docrag"
POSTGRES_USER = "docrag"
POSTGRES_PASSWORD = "docrag"

# Sample documents
SAMPLE_DOCUMENTS = [
    {
        "client_id": "CLIENT_001",
        "filename": "contract_2024_01.pdf",
        "fulltext": """# Договор поставки №123

Дата: 15.01.2024
Партнер: ООО Поставщик

## Финансовые условия

Сумма договора: 5,000,000 рублей
НДС: 18%
Общая сумма: 5,900,000 рублей

## Условия платежа

- Авансовый платеж: 30% при подписании
- Платеж по отгрузке: 70% при получении товара

## Риски

### Просрочки платежей

В истории отношений выявлены следующие просрочки:
- Платеж от 01.02.2023: просрочка на 15 дней
- Платеж от 15.03.2023: просрочка на 7 дней
- Штраф за просрочку: 0.5% в день от суммы

## Условия доставки

Доставка осуществляется транспортной компанией ООО Логистика.
Сроки доставки: 5-7 рабочих дней после отгрузки.
"""
    },
    {
        "client_id": "CLIENT_001",
        "filename": "invoice_2024_01.pdf",
        "fulltext": """# Счет-фактура №001

Дата: 20.01.2024

## Сумма счета

Сумма: 2,100,000 рублей

## НДС

НДС (20%): 420,000 рублей

## Итого к оплате

Итого: 2,520,000 рублей

## Реквизиты

Получатель: ООО Поставщик
ИНН: 7701234567
КПП: 770101001
Р/с: 40702810123456789012
"""
    }
]

SAMPLE_CHUNKS = [
    {
        "document_id": None,  # Will be set
        "client_id": "CLIENT_001",
        "chunk_index": 0,
        "text": "# Договор поставки №123\n\nДата: 15.01.2024\nПартнер: ООО Поставщик",
        "heading": "Договор поставки №123",
        "heading_level": 1,
        "chunk_type": "contract",
        "token_count": 25
    },
    {
        "document_id": None,
        "client_id": "CLIENT_001",
        "chunk_index": 1,
        "text": "## Финансовые условия\n\nСумма договора: 5,000,000 рублей\nНДС: 18%\nОбщая сумма: 5,900,000 рублей",
        "heading": "Финансовые условия",
        "heading_level": 2,
        "chunk_type": "financial",
        "token_count": 40
    },
    {
        "document_id": None,
        "client_id": "CLIENT_001",
        "chunk_index": 2,
        "text": "## Условия платежа\n\n- Авансовый платеж: 30% при подписании\n- Платеж по отгрузке: 70% при получении товара",
        "heading": "Условия платежа",
        "heading_level": 2,
        "chunk_type": "contract",
        "token_count": 35
    },
    {
        "document_id": None,
        "client_id": "CLIENT_001",
        "chunk_index": 3,
        "text": "## Риски\n\n### Просрочки платежей\n\nВ истории отношений выявлены следующие просрочки:\n- Платеж от 01.02.2023: просрочка на 15 дней\n- Платеж от 15.03.2023: просрочка на 7 дней\n- Штраф за просрочку: 0.5% в день от суммы",
        "heading": "Риски",
        "heading_level": 2,
        "chunk_type": "risk",
        "token_count": 80
    },
    {
        "document_id": None,
        "client_id": "CLIENT_001",
        "chunk_index": 4,
        "text": "## Условия доставки\n\nДоставка осуществляется транспортной компанией ООО Логистика.\nСроки доставки: 5-7 рабочих дней после отгрузки.",
        "heading": "Условия доставки",
        "heading_level": 2,
        "chunk_type": "contract",
        "token_count": 35
    }
]


def insert_sample_data():
    """Insert sample documents and chunks."""
    
    conn = psycopg2.connect(
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD
    )
    
    try:
        with conn.cursor() as cursor:
            # Insert documents
            document_ids = []
            for doc in SAMPLE_DOCUMENTS:
                document_id = str(uuid.uuid4())
                document_ids.append(document_id)
                
                cursor.execute("""
                    INSERT INTO documents (document_id, client_id, filename, fulltext, metadata, created_at)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    ON CONFLICT (document_id) DO NOTHING
                """, (
                    document_id,
                    doc["client_id"],
                    doc["filename"],
                    doc["fulltext"],
                    Json({"source": "test_data", "inserted_at": datetime.utcnow().isoformat()})
                ))
                print(f"Inserted document: {document_id} ({doc['filename']})")
            
            # Insert chunks for first document
            if document_ids:
                first_doc_id = document_ids[0]
                for chunk in SAMPLE_CHUNKS:
                    chunk_id = f"c_{first_doc_id[:8]}_{chunk['chunk_index']}"
                    
                    cursor.execute("""
                        INSERT INTO chunks (
                            chunk_id, document_id, client_id, chunk_index,
                            text, heading, heading_level, chunk_type, token_count, created_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                        ON CONFLICT (chunk_id) DO NOTHING
                    """, (
                        chunk_id,
                        first_doc_id,
                        chunk["client_id"],
                        chunk["chunk_index"],
                        chunk["text"],
                        chunk["heading"],
                        chunk["heading_level"],
                        chunk["chunk_type"],
                        chunk["token_count"]
                    ))
                    print(f"Inserted chunk: {chunk_id} ({chunk['heading']})")
            
            conn.commit()
            print("\nSample data inserted successfully!")
            print(f"Documents: {len(document_ids)}")
            print(f"Chunks: {len(SAMPLE_CHUNKS)}")
            
    finally:
        conn.close()


if __name__ == "__main__":
    insert_sample_data()
