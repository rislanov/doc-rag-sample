"""
Smart Document Processor - Hybrid MarkItDown + EasyOCR solution.

Handles digital documents (Word, Excel, PDF) via MarkItDown,
falls back to EasyOCR with intelligent Markdown reconstruction for scans.
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
    - EasyOCR for scans with intelligent Markdown reconstruction
    """

    # File extensions that MarkItDown handles well
    MARKITDOWN_EXTENSIONS = {'.pdf', '.docx', '.doc', '.xlsx', '.xls', 
                             '.pptx', '.ppt', '.html', '.htm', '.md', '.txt'}
    
    # Pure image extensions (always use OCR)
    IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.tif', '.webp'}
    
    # Minimum text length to consider MarkItDown successful
    MIN_VALID_TEXT_LENGTH = 50

    def __init__(self, ocr_languages: List[str] = None, use_gpu: bool = False):
        """
        Initialize processor with lazy loading of heavy components.
        
        Args:
            ocr_languages: Languages for OCR (default: Russian + English)
            use_gpu: Enable GPU for EasyOCR
        """
        self.ocr_languages = ocr_languages or ['ru', 'en']
        self.use_gpu = use_gpu
        
        # Lazy initialization - these are heavy
        self._markitdown = None
        self._easyocr_reader = None
        
        logger.info(f"DocumentProcessor initialized (OCR languages: {self.ocr_languages})")

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
        Process file with EasyOCR and intelligent Markdown reconstruction.
        """
        ext = os.path.splitext(file_path)[1].lower()
        
        # Handle multi-page PDFs
        if ext == '.pdf':
            return self._process_pdf_with_ocr(file_path)
        
        # Single image
        with open(file_path, 'rb') as f:
            image_bytes = f.read()
        
        text, details = self._ocr_image_to_markdown(image_bytes)
        
        return ProcessingResult(
            text=text,
            method=ProcessingMethod.EASYOCR,
            page_count=1,
            details=details
        )

    def _process_pdf_with_ocr(self, pdf_path: str) -> ProcessingResult:
        """
        Process PDF by converting pages to images and OCR-ing each.
        """
        try:
            from pdf2image import convert_from_path
            
            logger.info(f"Converting PDF to images for OCR: {pdf_path}")
            images = convert_from_path(pdf_path, dpi=200)
            
            all_text = []
            all_details = []
            
            for i, image in enumerate(images, 1):
                logger.info(f"Processing PDF page {i}/{len(images)}")
                
                # Convert PIL Image to bytes
                img_bytes = io.BytesIO()
                image.save(img_bytes, format='PNG')
                img_bytes = img_bytes.getvalue()
                
                page_text, page_details = self._ocr_image_to_markdown(img_bytes)
                
                all_text.append(f"## Страница {i}\n\n{page_text}")
                all_details.append({"page": i, "blocks": page_details.get("blocks_count", 0)})
            
            return ProcessingResult(
                text="\n\n---\n\n".join(all_text),
                method=ProcessingMethod.EASYOCR,
                page_count=len(images),
                details={"pages": all_details}
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
