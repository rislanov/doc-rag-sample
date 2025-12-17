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
    OCR_RESULT_QUEUE = os.getenv("OCR_RESULT_QUEUE", "ocr.results")
    CHUNKING_RESULT_QUEUE = os.getenv("CHUNKING_RESULT_QUEUE", "chunking.results")

    # Ollama LLM
    OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")
    
    # Embedding model (enbeddrus - specialized Russian/English embedding model)
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "evilfreelancer/enbeddrus")
    EMBEDDING_DIMENSION = int(os.getenv("EMBEDDING_DIMENSION", "768"))

    # Chunking settings
    CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))  # tokens
    CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))  # tokens

    @classmethod
    def get_postgres_dsn(cls) -> str:
        return f"postgresql://{cls.POSTGRES_USER}:{cls.POSTGRES_PASSWORD}@{cls.POSTGRES_HOST}:{cls.POSTGRES_PORT}/{cls.POSTGRES_DB}"
