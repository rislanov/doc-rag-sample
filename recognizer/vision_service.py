"""
Vision LLM Service for complex document understanding.

Uses Ollama vision models (MiniCPM-V, LLaVA) to extract structured text
from complex scans: tables, handwritten text, stamps over text, etc.
"""

import logging
import base64
import requests
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class VisionResult:
    """Result of vision model processing."""
    text: str
    model: str
    success: bool
    error: Optional[str] = None


class VisionService:
    """
    Vision LLM service for complex image understanding.
    
    Uses Ollama multimodal models to extract text with structure preservation.
    Best for: tables in scans, handwritten notes, stamps/signatures over text.
    """
    
    # Prompts for different document types
    PROMPTS = {
        "default": """Analyze this document image and extract ALL text content as Markdown.

Rules:
- Preserve document structure (headings, lists, paragraphs)
- Format tables as Markdown tables with | separators
- Keep numbers, dates, and amounts exactly as shown
- For handwritten text, transcribe as accurately as possible
- Mark unclear text with [неразборчиво] or [unclear]
- Use Russian for Russian documents, English for English

Output ONLY the extracted text in Markdown format, no explanations.""",

        "table": """Extract the table from this image as a Markdown table.

Rules:
- Use | for column separators
- Include header row with |---|---| separator
- Preserve all numbers and text exactly
- If cells are merged, expand them
- For empty cells, use empty space between ||

Output ONLY the Markdown table, nothing else.""",

        "passport": """Extract all text from this Russian passport/ID document.

Extract these fields if visible:
- ФИО (Full name)
- Дата рождения (Date of birth)
- Место рождения (Place of birth)
- Серия и номер (Series and number)
- Дата выдачи (Issue date)
- Кем выдан (Issued by)
- Код подразделения (Department code)

Format as structured Markdown with ## headers for each section.""",

        "handwritten": """Transcribe all handwritten text from this image.

Rules:
- Write exactly what you see, preserving spelling even if incorrect
- Mark uncertain words with [?]
- Preserve line breaks and paragraph structure
- Note any signatures as [подпись] or [signature]

Output the transcription in Markdown format."""
    }
    
    # Models in order of preference (faster/smaller first)
    VISION_MODELS = [
        "minicpm-v",      # Fast, good for documents
        "llava:7b",       # Good balance
        "llava:13b",      # Higher quality
        "bakllava",       # Alternative
    ]

    def __init__(
        self, 
        ollama_base_url: str = "http://localhost:11434",
        model: str = None,
        timeout: int = 120
    ):
        """
        Initialize Vision service.
        
        Args:
            ollama_base_url: Ollama API URL
            model: Specific model to use (auto-detect if None)
            timeout: Request timeout in seconds
        """
        self.base_url = ollama_base_url.rstrip('/')
        self.preferred_model = model
        self.timeout = timeout
        self._available_model = None
        
        logger.info(f"VisionService initialized (Ollama: {self.base_url})")

    def _get_available_model(self) -> Optional[str]:
        """Find first available vision model."""
        if self._available_model:
            return self._available_model
            
        if self.preferred_model:
            # Check if preferred model is available
            try:
                resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
                if resp.status_code == 200:
                    models = [m['name'] for m in resp.json().get('models', [])]
                    if any(self.preferred_model in m for m in models):
                        self._available_model = self.preferred_model
                        return self._available_model
            except Exception:
                pass
        
        # Try to find any vision model
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=10)
            if resp.status_code == 200:
                models = [m['name'] for m in resp.json().get('models', [])]
                for vision_model in self.VISION_MODELS:
                    if any(vision_model in m for m in models):
                        self._available_model = vision_model
                        logger.info(f"Found vision model: {vision_model}")
                        return self._available_model
        except Exception as e:
            logger.warning(f"Failed to check available models: {e}")
        
        return None

    def is_available(self) -> bool:
        """Check if vision service is available."""
        return self._get_available_model() is not None

    def process_image(
        self, 
        image_bytes: bytes, 
        prompt_type: str = "default",
        custom_prompt: str = None
    ) -> VisionResult:
        """
        Process image with vision model.
        
        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.)
            prompt_type: Type of extraction ("default", "table", "passport", "handwritten")
            custom_prompt: Override default prompt
            
        Returns:
            VisionResult with extracted text
        """
        model = self._get_available_model()
        if not model:
            return VisionResult(
                text="",
                model="none",
                success=False,
                error="No vision model available"
            )
        
        # Encode image to base64
        image_b64 = base64.b64encode(image_bytes).decode('utf-8')
        
        # Select prompt
        prompt = custom_prompt or self.PROMPTS.get(prompt_type, self.PROMPTS["default"])
        
        try:
            logger.info(f"Processing image with vision model {model}")
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "images": [image_b64],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temperature for accuracy
                        "num_predict": 4096,  # Allow long output for tables
                    }
                },
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                text = result.get('response', '').strip()
                
                if text:
                    logger.info(f"Vision extraction successful: {len(text)} chars")
                    return VisionResult(
                        text=text,
                        model=model,
                        success=True
                    )
                else:
                    return VisionResult(
                        text="",
                        model=model,
                        success=False,
                        error="Empty response from model"
                    )
            else:
                return VisionResult(
                    text="",
                    model=model,
                    success=False,
                    error=f"API error: {response.status_code}"
                )
                
        except requests.Timeout:
            return VisionResult(
                text="",
                model=model,
                success=False,
                error="Request timeout"
            )
        except Exception as e:
            logger.error(f"Vision processing failed: {e}")
            return VisionResult(
                text="",
                model=model,
                success=False,
                error=str(e)
            )

    def process_image_file(self, file_path: str, prompt_type: str = "default") -> VisionResult:
        """Process image file with vision model."""
        with open(file_path, 'rb') as f:
            return self.process_image(f.read(), prompt_type)

    def detect_document_type(self, image_bytes: bytes) -> str:
        """
        Detect document type for optimal prompt selection.
        
        Returns: "table", "passport", "handwritten", or "default"
        """
        model = self._get_available_model()
        if not model:
            return "default"
        
        try:
            image_b64 = base64.b64encode(image_bytes).decode('utf-8')
            
            response = requests.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": """Classify this document image. Reply with ONLY ONE word:
- TABLE (if contains a table or grid)
- PASSPORT (if it's an ID document, passport, driver's license)
- HANDWRITTEN (if contains significant handwritten text)
- DOCUMENT (for other typed documents)

Answer:""",
                    "images": [image_b64],
                    "stream": False,
                    "options": {"temperature": 0, "num_predict": 10}
                },
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json().get('response', '').strip().upper()
                if "TABLE" in result:
                    return "table"
                elif "PASSPORT" in result or "ID" in result:
                    return "passport"
                elif "HANDWRITTEN" in result or "HAND" in result:
                    return "handwritten"
                    
        except Exception as e:
            logger.warning(f"Document type detection failed: {e}")
        
        return "default"
