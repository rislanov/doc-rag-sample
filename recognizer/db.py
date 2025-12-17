import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager
from config import Config
import logging

logger = logging.getLogger(__name__)


class Database:
    """PostgreSQL database handler for storing OCR results."""

    def __init__(self):
        self.conn_params = {
            "host": Config.POSTGRES_HOST,
            "port": Config.POSTGRES_PORT,
            "dbname": Config.POSTGRES_DB,
            "user": Config.POSTGRES_USER,
            "password": Config.POSTGRES_PASSWORD,
        }

    @contextmanager
    def get_connection(self):
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

    def save_document_fulltext(
        self,
        document_id: str,
        client_id: str,
        filename: str,
        fulltext: str,
        metadata: dict = None,
    ) -> int:
        """
        Save OCR fulltext result to database.
        Returns the database record ID.
        """
        sql = """
        INSERT INTO documents (document_id, client_id, filename, fulltext, metadata, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
        ON CONFLICT (document_id) 
        DO UPDATE SET 
            fulltext = EXCLUDED.fulltext,
            metadata = EXCLUDED.metadata,
            updated_at = NOW()
        RETURNING id
        """

        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    sql,
                    (
                        document_id,
                        client_id,
                        filename,
                        fulltext,
                        psycopg2.extras.Json(metadata) if metadata else None,
                    ),
                )
                result = cursor.fetchone()
                return result[0]

    def get_document(self, document_id: str) -> dict:
        """Get document by document_id."""
        sql = """
        SELECT id, document_id, client_id, filename, fulltext, metadata, created_at, updated_at
        FROM documents
        WHERE document_id = %s
        """

        with self.get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cursor:
                cursor.execute(sql, (document_id,))
                return cursor.fetchone()

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
