#!/usr/bin/env python3
"""
Semantic Chunker Service - Document chunking worker.

Reads OCR results from RabbitMQ, chunks documents semantically,
generates embeddings via Ollama, saves chunks to PostgreSQL for RAG,
and publishes completion events.
"""

import logging
import signal
import sys
from datetime import datetime

from config import Config
from db import Database
from chunker import SemanticChunker
from embedding_service import EmbeddingService
from rabbitmq_handler import RabbitMQHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class ChunkerWorker:
    """Main worker class for semantic chunking with embeddings."""

    def __init__(self):
        logger.info("Initializing Semantic Chunker Worker...")
        
        self.db = Database()
        self.chunker = SemanticChunker()
        self.embedding_service = EmbeddingService()
        self.rabbitmq = RabbitMQHandler()
        
        self._embedding_available = False
        self._running = True
        self._setup_signal_handlers()
        self._check_embedding_service()

    def _check_embedding_service(self):
        """Check if embedding service is available."""
        if self.embedding_service.check_connection():
            self._embedding_available = True
            logger.info("Embedding service is available")
        else:
            self._embedding_available = False
            logger.warning("Embedding service not available - will store chunks without embeddings")

    def _setup_signal_handlers(self):
        """Setup graceful shutdown handlers."""
        signal.signal(signal.SIGINT, self._shutdown)
        signal.signal(signal.SIGTERM, self._shutdown)

    def _shutdown(self, signum, frame):
        """Handle shutdown signals."""
        logger.info("Shutdown signal received, stopping...")
        self._running = False
        self.rabbitmq.close()
        sys.exit(0)

    def process_ocr_result(self, message: dict):
        """
        Process OCR result and create semantic chunks.
        
        Expected message format (from Recognizer):
        {
            "status": "success",
            "document_id": "uuid-string",
            "client_id": "client-identifier",
            "db_id": 123,
            "text_length": 5000,
            "blocks_count": 45,
            "processed_at": "2024-01-15T10:30:00Z"
        }
        """
        document_id = message.get("document_id")
        client_id = message.get("client_id")

        if not document_id:
            logger.error("Missing document_id in message")
            return

        try:
            logger.info(f"Processing document {document_id} for chunking")
            
            # Fetch fulltext from database
            doc = self.db.get_document_fulltext(document_id)
            
            if not doc:
                logger.error(f"Document {document_id} not found in database")
                self._publish_error(document_id, "Document not found")
                return

            fulltext = doc.get("fulltext", "")
            client_id = client_id or doc.get("client_id")

            if not fulltext:
                logger.warning(f"Empty fulltext for document {document_id}")
                self._publish_error(document_id, "Empty document text")
              Generate embeddings for chunks
            if self._embedding_available:
                logger.info(f"Generating embeddings for {len(chunks)} chunks...")
                texts = [chunk["text"] for chunk in chunks]
                embeddings = self.embedding_service.embed_texts(texts)
                
                for chunk, embedding in zip(chunks, embeddings):
                    chunk["embedding"] = embedding
                
                embedded_count = sum(1 for e in embeddings if e is not None)
                logger.info(f"Generated {embedded_count}/{len(chunks)} embeddings")
            else:
                logger.info("Skipping embedding generation (service not available)")

            #   return

            # Perform semantic chunking
            chunks = self.chunker.chunk_document(
                text=fulltext,
                document_id=document_id,
                client_id=client_id
            )

            if not chunks:
                logger.warning(f"No chunks created for document {document_id}")
                self._publish_error(document_id, "No chunks created")
                return

            # Savembeddings_generated": self._embedding_available,
                "e chunks to database
            saved_count = self.db.save_chunks(chunks)
            
            # Update document metadata
            self.db.mark_document_chunked(document_id, saved_count)
            
            logger.info(f"Saved {saved_count} chunks for document {document_id}")

            # Publish success event
            self.rabbitmq.publish_result({
                "status": "success",
                "document_id": document_id,
                "client_id": client_id,
                "chunks_count": saved_count,
                "chunk_types": self._get_chunk_type_summary(chunks),
                "processed_at": datetime.utcnow().isoformat()
            })

        except Exception as e:
            logger.error(f"Failed to chunk document {document_id}: {e}")
            self._publish_error(document_id, str(e))

    def _get_chunk_type_summary(self, chunks: list) -> dict:
        """Get summary of chunk types."""
        summary = {}
        for chunk in chunks:
            chunk_type = chunk.get("chunk_type", "general")
            summary[chunk_type] = summary.get(chunk_type, 0) + 1
        return summary

    def _publish_error(self, document_id: str, error: str):
        """Publish error event."""
        self.rabbitmq.publish_result({
            "status": "error",
            "document_id": document_id,
            "error": error,
            "processed_at": datetime.utcnow().isoformat()
        })

    def run(self):
        """Start the worker."""
        logger.info("Starting Semantic Chunker Worker...")
        
        # Check database connection
        if not self.db.check_connection():
            logger.error("Database connection failed, exiting")
            sys.exit(1)
        
        logger.info("Database connection OK")
        logger.info("Waiting for OCR results...")
        
        # Start consuming messages
        self.rabbitmq.consume_ocr_results(self.process_ocr_result)


def main():
    worker = ChunkerWorker()
    worker.run()


if __name__ == "__main__":
    main()
