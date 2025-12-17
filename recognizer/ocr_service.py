import easyocr
import numpy as np
from PIL import Image
import io
import base64
import logging
from typing import List, Tuple, Optional
from config import Config

logger = logging.getLogger(__name__)


class OCRService:
    """EasyOCR-based document recognition service."""

    def __init__(self, languages: List[str] = None, gpu: bool = True):
        """
        Initialize EasyOCR reader.
        
        Args:
            languages: List of language codes (e.g., ['ru', 'en'])
            gpu: Use GPU acceleration if available
        """
        self.languages = languages or Config.OCR_LANGUAGES
        logger.info(f"Initializing EasyOCR with languages: {self.languages}")
        
        self.reader = easyocr.Reader(
            self.languages,
            gpu=gpu,
            verbose=False
        )
        logger.info("EasyOCR initialized successfully")

    def recognize_image(self, image_data: bytes) -> Tuple[str, List[dict]]:
        """
        Recognize text from image bytes.
        
        Args:
            image_data: Raw image bytes (PNG, JPEG, etc.)
            
        Returns:
            Tuple of (fulltext, details) where details contains bounding boxes and confidence
        """
        try:
            # Convert bytes to numpy array
            image = Image.open(io.BytesIO(image_data))
            image_np = np.array(image)

            # Run OCR
            results = self.reader.readtext(image_np)

            # Extract text and details
            text_lines = []
            details = []

            for bbox, text, confidence in results:
                text_lines.append(text)
                details.append({
                    "text": text,
                    "confidence": float(confidence),
                    "bbox": [[float(x) for x in point] for point in bbox]
                })

            fulltext = "\n".join(text_lines)
            
            logger.info(f"Recognized {len(results)} text blocks")
            return fulltext, details

        except Exception as e:
            logger.error(f"OCR recognition failed: {e}")
            raise

    def recognize_from_base64(self, base64_data: str) -> Tuple[str, List[dict]]:
        """
        Recognize text from base64-encoded image.
        
        Args:
            base64_data: Base64-encoded image string
            
        Returns:
            Tuple of (fulltext, details)
        """
        image_data = base64.b64decode(base64_data)
        return self.recognize_image(image_data)

    def recognize_file(self, file_path: str) -> Tuple[str, List[dict]]:
        """
        Recognize text from image file.
        
        Args:
            file_path: Path to image file
            
        Returns:
            Tuple of (fulltext, details)
        """
        with open(file_path, "rb") as f:
            image_data = f.read()
        return self.recognize_image(image_data)
