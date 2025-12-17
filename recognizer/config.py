import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # PostgreSQL
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = int(os.getenv("POSTGRES_PORT", "5432"))
    POSTGRES_DB = os.getenv("POSTGRES_DB", "docrag")
    POSTGRES_USER = os.getenv("POSTGRES_USER", "docrag")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD", "docrag")

    # RabbitMQ
    RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "localhost")
    RABBITMQ_PORT = int(os.getenv("RABBITMQ_PORT", "5672"))
    RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")
    RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")

    # Queues
    OCR_REQUEST_QUEUE = os.getenv("OCR_REQUEST_QUEUE", "ocr.requests")
    OCR_RESULT_QUEUE = os.getenv("OCR_RESULT_QUEUE", "ocr.results")

    # Document Processing
    OCR_LANGUAGES = ["ru", "en"]
    USE_GPU = os.getenv("USE_GPU", "false").lower() in ("true", "1", "yes")
    
    # Vision LLM (for complex scans: tables, handwritten, etc.)
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    VISION_MODEL = os.getenv("VISION_MODEL", "minicpm-v")  # or llava:7b
    USE_VISION_LLM = os.getenv("USE_VISION_LLM", "true").lower() in ("true", "1", "yes")
    
    # Vision LLM confidence threshold - use vision if OCR confidence below this
    VISION_CONFIDENCE_THRESHOLD = float(os.getenv("VISION_CONFIDENCE_THRESHOLD", "0.6"))

    @classmethod
    def get_postgres_dsn(cls) -> str:
        return f"postgresql://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
