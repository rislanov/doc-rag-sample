#!/usr/bin/env python3
"""
Test script to send OCR request to RabbitMQ.
Usage: python send_ocr_request.py <image_file>
"""

import sys
import base64
import json
import uuid
import pika

RABBITMQ_HOST = "localhost"
RABBITMQ_PORT = 5672
RABBITMQ_USER = "guest"
RABBITMQ_PASSWORD = "guest"
OCR_REQUEST_QUEUE = "ocr.requests"


def send_ocr_request(image_path: str, client_id: str = "TEST_CLIENT"):
    """Send OCR request to RabbitMQ."""
    
    # Read and encode image
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    
    # Create message
    document_id = str(uuid.uuid4())
    message = {
        "document_id": document_id,
        "client_id": client_id,
        "filename": image_path,
        "image_data": image_data,
        "page_number": 1
    }
    
    # Connect to RabbitMQ
    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)
    parameters = pika.ConnectionParameters(
        host=RABBITMQ_HOST,
        port=RABBITMQ_PORT,
        credentials=credentials
    )
    
    connection = pika.BlockingConnection(parameters)
    channel = connection.channel()
    
    # Declare queue
    channel.queue_declare(queue=OCR_REQUEST_QUEUE, durable=True)
    
    # Publish message
    channel.basic_publish(
        exchange="",
        routing_key=OCR_REQUEST_QUEUE,
        body=json.dumps(message, ensure_ascii=False),
        properties=pika.BasicProperties(
            delivery_mode=2,
            content_type="application/json"
        )
    )
    
    print(f"Sent OCR request for document: {document_id}")
    print(f"  Image: {image_path}")
    print(f"  Client: {client_id}")
    
    connection.close()
    return document_id


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python send_ocr_request.py <image_file> [client_id]")
        sys.exit(1)
    
    image_file = sys.argv[1]
    client_id = sys.argv[2] if len(sys.argv) > 2 else "TEST_CLIENT"
    
    send_ocr_request(image_file, client_id)
