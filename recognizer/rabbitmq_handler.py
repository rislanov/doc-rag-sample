import pika
import json
import logging
import time
from typing import Callable
from config import Config

logger = logging.getLogger(__name__)


class RabbitMQHandler:
    """RabbitMQ connection and message handler."""

    def __init__(self):
        self.connection = None
        self.channel = None
        self._connect()

    def _connect(self):
        """Establish connection to RabbitMQ with retry logic."""
        max_retries = 10
        retry_delay = 5

        for attempt in range(max_retries):
            try:
                credentials = pika.PlainCredentials(
                    Config.RABBITMQ_USER,
                    Config.RABBITMQ_PASSWORD
                )
                parameters = pika.ConnectionParameters(
                    host=Config.RABBITMQ_HOST,
                    port=Config.RABBITMQ_PORT,
                    credentials=credentials,
                    heartbeat=600,
                    blocked_connection_timeout=300
                )

                self.connection = pika.BlockingConnection(parameters)
                self.channel = self.connection.channel()

                # Declare queues
                self.channel.queue_declare(queue=Config.OCR_REQUEST_QUEUE, durable=True)
                self.channel.queue_declare(queue=Config.OCR_RESULT_QUEUE, durable=True)

                # Set prefetch count for fair dispatch
                self.channel.basic_qos(prefetch_count=1)

                logger.info("Connected to RabbitMQ successfully")
                return

            except pika.exceptions.AMQPConnectionError as e:
                logger.warning(f"RabbitMQ connection attempt {attempt + 1}/{max_retries} failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                else:
                    raise

    def _ensure_connection(self):
        """Ensure connection is alive, reconnect if needed."""
        if self.connection is None or self.connection.is_closed:
            self._connect()
        if self.channel is None or self.channel.is_closed:
            self.channel = self.connection.channel()

    def publish_result(self, message: dict):
        """
        Publish OCR result to results queue.
        
        Args:
            message: Result message dict containing document_id, status, etc.
        """
        self._ensure_connection()
        
        self.channel.basic_publish(
            exchange="",
            routing_key=Config.OCR_RESULT_QUEUE,
            body=json.dumps(message, ensure_ascii=False),
            properties=pika.BasicProperties(
                delivery_mode=2,  # Persistent
                content_type="application/json"
            )
        )
        logger.info(f"Published result for document: {message.get('document_id')}")

    def consume_requests(self, callback: Callable):
        """
        Start consuming OCR requests.
        
        Args:
            callback: Function to call for each message (body: dict) -> None
        """
        self._ensure_connection()

        def on_message(channel, method, properties, body):
            try:
                message = json.loads(body)
                logger.info(f"Received OCR request for document: {message.get('document_id')}")
                
                callback(message)
                
                channel.basic_ack(delivery_tag=method.delivery_tag)
                
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in message: {e}")
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=False)
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                channel.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

        self.channel.basic_consume(
            queue=Config.OCR_REQUEST_QUEUE,
            on_message_callback=on_message
        )

        logger.info(f"Started consuming from {Config.OCR_REQUEST_QUEUE}")
        self.channel.start_consuming()

    def close(self):
        """Close RabbitMQ connection."""
        if self.connection and not self.connection.is_closed:
            self.connection.close()
            logger.info("RabbitMQ connection closed")
