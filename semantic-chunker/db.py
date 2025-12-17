import psycopg2
from psycopg2.extras import RealDictCursor, execute_values
from pgvector.psycopg2 import register_vector
from contextlib import contextmanager
from config import Config
from typing import List, Dict, Optional
import logging
import numpy as np

logger = logging.getLogger(__name__)


class Database:
    """PostgreSQL database handler for storing chunks and retrieving documents."""

    def __init__(self):
        self.conn_params = {
            "host": Config.POSTGRES_HOST,
            "port": Config.POSTGRES_PORT,
            "dbname": Config.POSTGRES_DB,
            "user": Config.POSTGRES_USER,
            "password": Config.POSTGRES_PASSWORD,
        }

    @contextmanager
    def # Register pgvector type
        register_vector(conn)
        get_connection(self):
        conn = psycopg2.connect(**self.conn_params)
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            conn.close()

    def get_document_fulltext(self, document_id: str) -> Optional[Dict]:
        """Get document fulltext by document_id."""
        sql = """
        SELECT id, document_id, client_id, filename, fulltext, metadata, created_at
        FROM documents
        WHERE document_id = %s
        """

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, (document_id,))
                result = cursor.fetchone()
                return dict(result) if result else None

    def save_chunks(self, chunks: List[Dict]) -> int:
        """
        Save chunks to database.
        
        Expected chunk format:
        {
            "chunk_id": "c_doc123_0",
            "document_id": "doc123",
            "client_id": "client1",
            "chunk_index": 0,
            "text": "chunk text...",
            "heading": "Section Title",
            "heading_level": 2,
            "embedding": [0.1, 0.2, ...]  # optional
        }
        
        Returns number of chunks inserted.
        """
        if not chunks:
            return 0

        sql = """
        INSERT INTO chunks (
            chunk_id, document_id, client_id, chunk_index, 
            text, heading, heading_level, chunk_type, token_count, embedding, created_at
        ) VALUES %s
        ON CONFLICT (chunk_id) DO UPDATE SET
            text = EXCLUDED.text,
            heading = EXCLUDED.heading,
            heading_level = EXCLUDED.heading_level,
            chunk_type = EXCLUDED.chunk_type,
            token_count = EXCLUDED.token_count,
            embedding = EXCLUDED.embedding,
            updated_at = NOW()
        """

        values = [
            (
                chunk["chunk_id"],
                chunk["document_id"],
                chunk["client_id"],
                chunk["chunk_index"],
                chunk["text"],
                chunk.get("heading"),
                chunk.get("heading_level", 0),
                chunk.get("chunk_type", "general"),
                chunk.get("token_count", 0),
                np.array(chunk["embedding"]) if chunk.get("embedding") else None0),
                chunk.get("chunk_type", "general"),
                chunk.get("token_count", 0),
            )
            for chunk in chunks
        ]

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                execute_values(cursor, sql, values)
                return len(values)

    def mark_document_chunked(self, document_id: str, chunk_count: int):
        """Update document with chunking status."""
        sql = """
        UPDATE documents 
        SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
            updated_at = NOW()
        WHERE document_id = %s
        """

        metadata_update = {
            "chunked": True,
            "chunk_count": chunk_count
        }

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(sql, (psycopg2.extras.Json(metadata_update), document_id))

    def check_connection(self) -> bool:
        """Check database connection."""
        try:
            with self.get_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT 1")
                    return True
        except Exception as e:
            logger.error(f"Database connection check failed: {e}")
            return False
