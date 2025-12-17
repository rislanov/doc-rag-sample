#!/usr/bin/env python3
"""
Recognizer Service - Smart document processing worker.

Reads OCR requests from RabbitMQ, processes documents with MarkItDown + EasyOCR,
saves fulltext (Markdown) to PostgreSQL, and publishes completion events.
"""

import logging
import signal
import sys
import base64
from datetime import datetime

from config import Config
from db import Database
from document_processor import DocumentProcessor, ProcessingMethod
from rabbitmq_handler import RabbitMQHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class RecognizerWorker:
    """Main worker class for document processing."""

    def __init__(self):
        logger.info("Initializing Recognizer Worker...")
        
        self.db = Database()
        self.processor = DocumentProcessor(
            ocr_languages=Config.OCR_LANGUAGES,
            use_gpu=Config.USE_GPU
        )
        self.rabbitmq = RabbitMQHandler()
        
        self._running = True
        self._setup_signal_handlers()

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

    def process_ocr_request(self, message: dict):
        """
        Process a single document request.
        
        Expected message format:
        {
            "document_id": "uuid-string",
            "client_id": "client-identifier",
            "filename": "document.pdf",
            "image_data": "base64-encoded-file",
            "page_number": 1  # optional, for legacy compatibility
        }
        """
        document_id = message.get("document_id")
        client_id = message.get("client_id")
        filename = message.get("filename", "unknown.jpg")
        image_data = message.get("image_data")
        page_number = message.get("page_number", 1)

        if not document_id or not image_data:
            logger.error("Missing required fields: document_id or image_data")
            self._publish_error(document_id, "Missing required fields")
            return

        try:
            logger.info(f"Processing document {document_id}: {filename}")
            
            # Decode file data
            file_bytes = base64.b64decode(image_data)
            
            # Process with smart document processor
            result = self.processor.process_bytes(file_bytes, filename)
            
            logger.info(
                f"Processed {document_id} with {result.method.value}: "
                f"{len(result.text)} chars, {result.page_count} pages"
            )
            
            # Build metadata
            metadata = {
                "page_number": page_number,
                "processing_method": result.method.value,
                "page_count": result.page_count,
                "details": result.details,
                "processed_at": datetime.utcnow().isoformat()
            }
            
            # Save to database (now stores Markdown-formatted text)
            db_id = self.db.save_document_fulltext(
                document_id=document_id,
                client_id=client_id,
                filename=filename,
                fulltext=result.text,
                metadata=metadata
            )
            
            logger.info(f"Saved document {document_id} with DB ID {db_id}")
            
            # Publish success event
            self.rabbitmq.publish_result({
                "status": "success",
                "document_id": document_id,
                "client_id": client_id,
                "db_id": db_id,
                "text_length": len(result.text),
                "page_count": result.page_count,
                "processing_method": result.method.value,
                "processed_at": datetime.utcnow().isoformat()
            })

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {e}")
            self._publish_error(document_id, str(e))

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
        logger.info("Starting Recognizer Worker...")
        
        # Check database connection
        if not self.db.check_connection():
            logger.error("Database connection failed, exiting")
            sys.exit(1)
        
        logger.info("Database connection OK")
        logger.info("Waiting for OCR requests...")
        
        # Start consuming messages
        self.rabbitmq.consume_requests(self.process_ocr_request)


def main():
    worker = RecognizerWorker()
    worker.run()


if __name__ == "__main__":
    main()
