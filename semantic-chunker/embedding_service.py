import requests
import logging
from typing import List, Optional
from config import Config

logger = logging.getLogger(__name__)


class EmbeddingService:
    """
    Ollama embedding service for semantic search.
    Uses nomic-embed-text or mxbai-embed-large models.
    """

    def __init__(
        self, 
        base_url: str = None, 
        model: str = None,
        timeout: int = 60
    ):
        """
        Initialize embedding service.
        
        Args:
            base_url: Ollama API base URL
            model: Embedding model name
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or Config.OLLAMA_BASE_URL
        self.model = model or Config.EMBEDDING_MODEL
        self.timeout = timeout
        self._dimension = None
        
        logger.info(f"Initialized EmbeddingService with model: {self.model}")

    @property
    def dimension(self) -> int:
        """Get embedding dimension (cached after first call)."""
        if self._dimension is None:
            # Get dimension by making a test embedding
            test_embedding = self.embed_text("test")
            if test_embedding:
                self._dimension = len(test_embedding)
            else:
                # Default dimensions for common models
                if "nomic" in self.model:
                    self._dimension = 768
                elif "mxbai" in self.model:
                    self._dimension = 1024
                else:
                    self._dimension = 768
        return self._dimension

    def embed_text(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats (embedding vector) or None on error
        """
        if not text or not text.strip():
            return None

        try:
            response = requests.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text[:8000]  # Truncate very long texts
                },
                timeout=self.timeout
            )
            response.raise_for_status()
            
            result = response.json()
            embedding = result.get("embedding")
            
            if embedding:
                logger.debug(f"Generated embedding of dimension {len(embedding)}")
                return embedding
            else:
                logger.warning("Empty embedding returned from Ollama")
                return None

        except requests.exceptions.Timeout:
            logger.error(f"Timeout generating embedding for text of length {len(text)}")
            return None
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to generate embedding: {e}")
            return None

    def embed_texts(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts.
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings (some may be None on error)
        """
        embeddings = []
        
        for i, text in enumerate(texts):
            embedding = self.embed_text(text)
            embeddings.append(embedding)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Generated {i + 1}/{len(texts)} embeddings")
        
        successful = sum(1 for e in embeddings if e is not None)
        logger.info(f"Generated {successful}/{len(texts)} embeddings successfully")
        
        return embeddings

    def check_connection(self) -> bool:
        """Check if Ollama embedding service is available."""
        try:
            response = requests.get(
                f"{self.base_url}/api/tags",
                timeout=5
            )
            response.raise_for_status()
            
            # Check if embedding model is available
            models = response.json().get("models", [])
            model_names = [m.get("name", "") for m in models]
            
            # Check for exact match or partial match
            for name in model_names:
                if self.model in name or name in self.model:
                    logger.info(f"Embedding model {self.model} is available")
                    return True
            
            logger.warning(f"Embedding model {self.model} not found. Available: {model_names}")
            return False

        except Exception as e:
            logger.error(f"Failed to check Ollama connection: {e}")
            return False
