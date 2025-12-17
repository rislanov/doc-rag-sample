"""
Smart Document Processor - Hybrid MarkItDown + EasyOCR + Vision LLM solution.

Handles digital documents (Word, Excel, PDF) via MarkItDown,
uses EasyOCR for simple scans, and Vision LLM for complex scans (tables, handwriting).
"""

import logging
import os
import tempfile
import statistics
from typing import Tuple, List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
from PIL import Image
import numpy as np
import io

logger = logging.getLogger(__name__)


class ProcessingMethod(Enum):
    """Document processing method used."""
    MARKITDOWN = "markitdown"
    EASYOCR = "easyocr"
    VISION_LLM = "vision_llm"
    HYBRID = "hybrid"  # MarkItDown + OCR for embedded images


@dataclass
class ProcessingResult:
    """Result of document processing."""
    text: str
    method: ProcessingMethod
    page_count: int
    details: Dict[str, Any]


class DocumentProcessor:
    """
    Smart document processor that chooses the best strategy:
    - MarkItDown for digital documents (preserves structure)
    - EasyOCR for simple scans with intelligent Markdown reconstruction
    - Vision LLM for complex scans (tables, handwritten text, low OCR confidence)
    """

    # File extensions that MarkItDown handles well
    MARKITDOWN_EXTENSIONS = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', 
                             '.pptx', '.ppt', '.html', '.htm', '.md', '.txt'}
    
    # Pure image extensions (always use OCR/Vision)
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
    
    # Minimum text length to consider MarkItDown successful
    MIN_VALID_TEXT_LENGTH = 50
    
    # OCR confidence threshold - below this, try Vision LLM
    DEFAULT_VISION_THRESHOLD = 0.6

    def __init__(
        self, 
        ocr_languages: List[str] = None, 
        use_gpu: bool = False,
        use_vision_llm: bool = True,
        ollama_base_url: str = None,
        vision_model: str = None,
        vision_confidence_threshold: float = None
    ):
        """
        Initialize processor with lazy loading of heavy components.
        
        Args:
            ocr_languages: Languages for OCR (default: Russian + English)
            use_gpu: Enable GPU for EasyOCR
            use_vision_llm: Enable Vision LLM for complex scans
            ollama_base_url: Ollama API URL for Vision LLM
            vision_model: Vision model name (minicpm-v, llava)
            vision_confidence_threshold: OCR confidence threshold for Vision fallback
        """
        self.ocr_languages = ocr_languages or ['ru', 'en']
        self.use_gpu = use_gpu
        self.use_vision_llm = use_vision_llm
        self.ollama_base_url = ollama_base_url or "http://localhost:11434"
        self.vision_model = vision_model
        self.vision_threshold = vision_confidence_threshold or self.DEFAULT_VISION_THRESHOLD
        
        # Lazy initialization - these are heavy
        self._markitdown = None
        self._easyocr_reader = None
        self._vision_service = None
        
        logger.info(f"DocumentProcessor initialized (OCR: {self.ocr_languages}, Vision: {use_vision_llm})")

    @property
    def markitdown(self):
        """Lazy load MarkItDown."""
        if self._markitdown is None:
            from markitdown import MarkItDown
            self._markitdown = MarkItDown()
            logger.info("MarkItDown initialized")
        return self._markitdown

    @property
    def ocr_reader(self):
        """Lazy load EasyOCR (heavy operation)."""
        if self._easyocr_reader is None:
            import easyocr
            logger.info("Initializing EasyOCR (this may take a moment)...")
            self._easyocr_reader = easyocr.Reader(
                self.ocr_languages, 
                gpu=self.use_gpu,
                verbose=False
            )
            logger.info("EasyOCR initialized")
        return self._easyocr_reader

    @property
    def vision_service(self):
        """Lazy load Vision LLM service."""
        if self._vision_service is None and self.use_vision_llm:
            from vision_service import VisionService
            self._vision_service = VisionService(
                ollama_base_url=self.ollama_base_url,
                model=self.vision_model
            )
            logger.info("VisionService initialized")
        return self._vision_service)
        return self._easyocr_reader

    def process_bytes(self, file_bytes: bytes, filename: str) -> ProcessingResult:
        """
        Process document from bytes.
        
        Args:
            file_bytes: Raw file content
            filename: Original filename (used to detect format)
            
        Returns:
            ProcessingResult with Markdown text and metadata
        """
        ext = os.path.splitext(filename)[1].lower()
        
        # Write to temp file for processing
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name
        
        try:
            return self.process_file(tmp_path, ext)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def process_file(self, file_path: str, extension: str = None) -> ProcessingResult:
        """
        Process document file with automatic strategy selection.
        
        Args:
            file_path: Path to the file
            extension: File extension (detected from path if not provided)
            
        Returns:
            ProcessingResult with Markdown text and metadata
        """
        ext = (extension or os.path.splitext(file_path)[1]).lower()
        
        # Strategy 1: Pure images -> OCR only
        if ext in self.IMAGE_EXTENSIONS:
            logger.info(f"Processing image with OCR: {file_path}")
            return self._process_with_ocr(file_path)
        
        # Strategy 2: Digital documents -> Try MarkItDown first
        if ext in self.MARKITDOWN_EXTENSIONS:
            logger.info(f"Trying MarkItDown for: {file_path}")
            result = self._try_markitdown(file_path)
            
            if result:
                return result
            
            # Fallback: MarkItDown failed (probably scanned PDF)
            logger.info(f"MarkItDown produced insufficient text, falling back to OCR")
            return self._process_with_ocr(file_path)
        
        # Strategy 3: Unknown format -> try OCR
        logger.warning(f"Unknown format '{ext}', attempting OCR")
        return self._process_with_ocr(file_path)

    def _try_markitdown(self, file_path: str) -> Optional[ProcessingResult]:
        """
        Attempt to process with MarkItDown.
        
        Returns None if extraction fails or produces too little text.
        """
        try:
            result = self.markitdown.convert(file_path)
            
            if result.text_content and len(result.text_content.strip()) >= self.MIN_VALID_TEXT_LENGTH:
                # Clean up the markdown
                text = self._clean_markdown(result.text_content)
                
                return ProcessingResult(
                    text=text,
                    method=ProcessingMethod.MARKITDOWN,
                    page_count=1,  # MarkItDown doesn't expose page count
                    details={
                        "original_length": len(result.text_content),
                        "cleaned_length": len(text)
                    }
                )
            
            return None
            
        except Exception as e:
            logger.warning(f"MarkItDown failed: {e}")
            return None

    def _process_with_ocr(self, file_path: str) -> ProcessingResult:
        """
        Process file with EasyOCR, with Vision LLM fallback for complex images.
        
        Strategy:
        1. Try EasyOCR first (fast)
        2. If confidence is low OR text is short, try Vision LLM
        3. Use best result
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        # Handle multi-page PDFs
        if ext == '.pdf':
            return self._process_pdf_with_ocr(file_path)
        
        # Single image
        with open(file_path, 'rb') as f:
            image_bytes = f.read()
        
        # Step 1: Try EasyOCR
        ocr_text, ocr_details = self._ocr_image_to_markdown(image_bytes)
        ocr_confidence = ocr_details.get('confidence', 0)
        
        # Step 2: Decide if we need Vision LLM
        use_vision = False
        vision_reason = None
        
        if self.use_vision_llm and self.vision_service and self.vision_service.is_available():
            # Low confidence -> try vision
            if ocr_confidence < self.vision_threshold:
                use_vision = True
                vision_reason = f"low_confidence ({ocr_confidence:.2f} < {self.vision_threshold})"
            # Very short text (might have missed content)
            elif len(ocr_text) < 100 and ocr_details.get('blocks_count', 0) < 5:
                use_vision = True
                vision_reason = "short_text"
        
        # Step 3: Try Vision LLM if needed
        if use_vision:
            logger.info(f"Trying Vision LLM (reason: {vision_reason})")
            
            # Detect document type for optimal prompt
            doc_type = self.vision_service.detect_document_type(image_bytes)
            vision_result = self.vision_service.process_image(image_bytes, prompt_type=doc_type)
            
            if vision_result.success and len(vision_result.text) > len(ocr_text):
                logger.info(f"Vision LLM produced better result: {len(vision_result.text)} vs {len(ocr_text)} chars")
                return ProcessingResult(
                    text=vision_result.text,
                    method=ProcessingMethod.VISION_LLM,
                    page_count=1,
                    details={
                        "vision_model": vision_result.model,
                        "document_type": doc_type,
                        "ocr_confidence": ocr_confidence,
                        "ocr_text_length": len(ocr_text),
                        "vision_reason": vision_reason
                    }
                )
            else:
                logger.info("Vision LLM didn't improve result, using OCR output")
        
        return ProcessingResult(
            text=ocr_text,
            method=ProcessingMethod.EASYOCR,
            page_count=1,
            details=ocr_details
        )

    def _process_pdf_with_ocr(self, pdf_path: str) -> ProcessingResult:
        """
        Process PDF by converting pages to images and OCR-ing each.
        Uses Vision LLM for pages with low OCR confidence.
        """
        try:
            from pdf2image import convert_from_path
            
            logger.info(f"Converting PDF to images for OCR: {pdf_path}")
            images = convert_from_path(pdf_path, dpi=200)
            
            all_text = []
            all_details = []
            methods_used = set()
            
            for i, image in enumerate(images, 1):
                logger.info(f"Processing PDF page {i}/{len(images)}")
                
                # Convert PIL Image to bytes
                img_bytes = io.BytesIO()
                image.save(img_bytes, format='PNG')
                img_bytes = img_bytes.getvalue()
                
                # Try OCR first
                page_text, page_details = self._ocr_image_to_markdown(img_bytes)
                ocr_confidence = page_details.get('confidence', 0)
                method = "easyocr"
                
                # Try Vision LLM if OCR confidence is low
                if (self.use_vision_llm and self.vision_service and 
                    self.vision_service.is_available() and 
                    ocr_confidence < self.vision_threshold):
                    
                    logger.info(f"Page {i}: Low OCR confidence ({ocr_confidence:.2f}), trying Vision LLM")
                    doc_type = self.vision_service.detect_document_type(img_bytes)
                    vision_result = self.vision_service.process_image(img_bytes, prompt_type=doc_type)
                    
                    if vision_result.success and len(vision_result.text) > len(page_text):
                        page_text = vision_result.text
                        method = "vision_llm"
                        logger.info(f"Page {i}: Using Vision LLM result")
                
                methods_used.add(method)
                all_text.append(f"## Страница {i}\n\n{page_text}")
                all_details.append({
                    "page": i, 
                    "blocks": page_details.get("blocks_count", 0),
                    "confidence": ocr_confidence,
                    "method": method
                })
            
            # Determine overall method
            if "vision_llm" in methods_used and "easyocr" in methods_used:
                overall_method = ProcessingMethod.HYBRID
            elif "vision_llm" in methods_used:
                overall_method = ProcessingMethod.VISION_LLM
            else:
                overall_method = ProcessingMethod.EASYOCR
            
            return ProcessingResult(
                text="\n\n---\n\n".join(all_text),
                method=overall_method,
                page_count=len(images),
                details={"pages": all_details, "methods_used": list(methods_used)}
            )
            
        except ImportError:
            logger.warning("pdf2image not available, trying direct OCR")
            # Fallback: try to OCR the PDF directly (works for single-page)
            with open(pdf_path, 'rb') as f:
                return self._ocr_image_to_markdown(f.read())[0]
        except Exception as e:
            logger.error(f"PDF OCR failed: {e}")
            raise

    def _ocr_image_to_markdown(self, image_bytes: bytes) -> Tuple[str, Dict]:
        """
        Perform OCR and reconstruct Markdown structure from visual layout.
        
        Uses heuristics:
        - Large text height -> Heading
        - ALL CAPS short text -> Heading
        - Aligned blocks -> Possible table
        - Indented text -> List item
        """
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image_np = np.array(image)
        except Exception:
            # Might be a PDF or other format, try direct
            image_np = image_bytes
        
        # Run OCR with detailed output
        results = self.ocr_reader.readtext(image_np, detail=1)
        
        if not results:
            return "", {"blocks_count": 0, "confidence": 0}
        
        # Sort by Y (top to bottom), then X (left to right)
        results.sort(key=lambda x: (x[0][0][1], x[0][0][0]))
        
        # Calculate text height statistics for heading detection
        heights = [self._get_bbox_height(r[0]) for r in results]
        median_height = statistics.median(heights) if heights else 20
        
        # Build Markdown lines
        lines = []
        prev_y = None
        
        for bbox, text, confidence in results:
            if confidence < 0.3:
                continue
            
            text = text.strip()
            if not text:
                continue
            
            height = self._get_bbox_height(bbox)
            y_pos = bbox[0][1]
            
            # Detect paragraph breaks (large Y gap)
            if prev_y is not None and (y_pos - prev_y) > median_height * 2:
                lines.append("")  # Empty line for paragraph break
            
            # Heading detection heuristics
            is_heading = False
            heading_level = "##"
            
            # Heuristic 1: Significantly larger than median
            if height > median_height * 1.5:
                is_heading = True
                if height > median_height * 2:
                    heading_level = "#"
            
            # Heuristic 2: Short ALL CAPS text
            if len(text) < 50 and text.isupper() and len(text.split()) <= 6:
                is_heading = True
            
            # Heuristic 3: Numbered section (e.g., "1. Введение", "Раздел 2")
            if self._looks_like_section_header(text):
                is_heading = True
            
            if is_heading:
                lines.append(f"{heading_level} {text}")
            else:
                lines.append(text)
            
            prev_y = y_pos + height

        # Join and clean up
        markdown_text = "\n\n".join(lines)
        markdown_text = self._clean_markdown(markdown_text)
        
        avg_confidence = sum(r[2] for r in results) / len(results)
        
        return markdown_text, {
            "blocks_count": len(results),
            "confidence": round(avg_confidence, 3),
            "median_height": round(median_height, 1)
        }

    def _get_bbox_height(self, bbox) -> float:
        """Calculate height of bounding box."""
        return abs(bbox[2][1] - bbox[0][1])

    def _looks_like_section_header(self, text: str) -> bool:
        """Check if text looks like a section header."""
        import re
        patterns = [
            r'^[0-9]+\.\s+[А-ЯA-Z]',  # "1. Введение"
            r'^Раздел\s+[0-9]+',       # "Раздел 1"
            r'^Глава\s+[0-9]+',        # "Глава 1"
            r'^Section\s+[0-9]+',      # "Section 1"
            r'^Chapter\s+[0-9]+',      # "Chapter 1"
            r'^Приложение\s+[0-9A-Za-zА-Яа-я]+',  # "Приложение А"
        ]
        return any(re.match(p, text, re.IGNORECASE) for p in patterns)

    def _clean_markdown(self, text: str) -> str:
        """Clean up Markdown text."""
        import re
        
        # Remove excessive blank lines
        text = re.sub(r'\n{4,}', '\n\n\n', text)
        
        # Fix common OCR artifacts
        text = re.sub(r'[|]{2,}', '|', text)  # Multiple pipes
        text = re.sub(r'[-]{5,}', '---', text)  # Long dashes
        
        # Trim whitespace
        text = '\n'.join(line.rstrip() for line in text.split('\n'))
        
        return text.strip()
