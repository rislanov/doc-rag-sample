import re
import tiktoken
from typing import List, Dict, Optional, Tuple
import logging
from config import Config

logger = logging.getLogger(__name__)


class SemanticChunker:
    """
    Semantic chunker for markdown documents.
    
    - Parses markdown by heading structure
    - Token-aware semantic splitting (~500 tokens per chunk)
    - Chunk type inference based on heading and content
    """

    # Chunk type keywords for inference
    # Порядок важен: более специфичные типы идут первыми
    CHUNK_TYPE_PATTERNS = {
        # Документы, удостоверяющие личность
        "passport": [
            r"паспорт", r"серия", r"номер паспорт", r"выдан", r"код подразделения",
            r"место рождения", r"дата рождения", r"гражданин", r"удостоверяющ",
            r"passport", r"ФИО", r"фамилия.*имя.*отчество"
        ],
        # Налоговые документы
        "ndfl": [
            r"ндфл", r"2-ндфл", r"3-ндфл", r"справка о доходах", r"налоговый агент",
            r"налогооблагаем", r"вычет", r"удержан", r"исчислен", r"налоговая база",
            r"сумма дохода", r"код дохода"
        ],
        # Анкетные данные
        "questionnaire": [
            r"анкет", r"заявлени", r"персональные данные", r"согласие на обработку",
            r"семейное положение", r"образование", r"место работы", r"должность",
            r"стаж", r"контактные данные", r"телефон", r"email", r"адрес проживания"
        ],
        # Банковские документы
        "bank_statement": [
            r"выписка", r"банковск", r"остаток", r"оборот", r"дебет", r"кредит",
            r"расчетный счет", r"корреспондент", r"БИК", r"swift"
        ],
        # Кредитные документы
        "credit": [
            r"кредит", r"займ", r"ссуда", r"процентная ставка", r"график платежей",
            r"погашение", r"задолженност", r"лимит", r"кредитная история"
        ],
        # Трудовые документы
        "employment": [
            r"трудов", r"работодатель", r"заработн", r"оклад", r"премия",
            r"трудоустро", r"увольнени", r"приказ", r"табель"
        ],
        # Имущественные документы
        "property": [
            r"недвижимост", r"собственност", r"кадастр", r"ЕГРН", r"право собственности",
            r"квартир", r"дом", r"земельн", r"площадь", r"объект недвижимости"
        ],
        # Договоры
        "contract": [
            r"договор", r"контракт", r"соглашение", r"условия договора", 
            r"обязательств", r"сторон", r"подписан", r"срок действия"
        ],
        # Счета и платежи
        "invoice": [
            r"счет", r"счёт", r"фактура", r"оплат", r"платеж", 
            r"invoice", r"payment", r"к оплате", r"реквизиты"
        ],
        # Риски
        "risk": [
            r"риск", r"просрочк", r"штраф", r"пени", r"нарушени",
            r"угроз", r"опасност", r"дефолт", r"неплатеж"
        ],
        # Финансовые данные
        "financial": [
            r"сумм", r"стоимост", r"цен", r"бюджет", r"финанс",
            r"рубл", r"доллар", r"евро", r"валют", r"итого"
        ],
    }

    def __init__(self, chunk_size: int = None, chunk_overlap: int = None):
        """
        Initialize chunker.
        
        Args:
            chunk_size: Target chunk size in tokens (default from config)
            chunk_overlap: Overlap between chunks in tokens (default from config)
        """
        self.chunk_size = chunk_size or Config.CHUNK_SIZE
        self.chunk_overlap = chunk_overlap or Config.CHUNK_OVERLAP
        
        # Use cl100k_base encoding (similar to GPT-4, works well for most models)
        try:
            self.tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            logger.warning("Failed to load cl100k_base, using approximate counting")
            self.tokenizer = None

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if self.tokenizer:
            return len(self.tokenizer.encode(text))
        # Approximate: ~4 chars per token for Russian
        return len(text) // 4

    def infer_chunk_type(self, heading: str, text: str) -> str:
        """
        Infer chunk type from heading and content.
        
        Returns one of: contract, invoice, risk, financial, general
        """
        combined = f"{heading or ''} {text}".lower()
        
        for chunk_type, patterns in self.CHUNK_TYPE_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, combined):
                    return chunk_type
        
        return "general"

    def parse_headings(self, text: str) -> List[Dict]:
        """
        Parse markdown into sections based on headings.
        
        Returns list of sections:
        [
            {
                "heading": "Title",
                "heading_level": 1,
                "content": "section content...",
                "start_line": 0
            }
        ]
        """
        lines = text.split("\n")
        sections = []
        current_section = {
            "heading": None,
            "heading_level": 0,
            "content_lines": [],
            "start_line": 0
        }

        heading_pattern = re.compile(r"^(#{1,6})\s+(.+)$")

        for i, line in enumerate(lines):
            match = heading_pattern.match(line)
            
            if match:
                # Save previous section if it has content
                if current_section["content_lines"] or current_section["heading"]:
                    content = "\n".join(current_section["content_lines"]).strip()
                    if content or current_section["heading"]:
                        sections.append({
                            "heading": current_section["heading"],
                            "heading_level": current_section["heading_level"],
                            "content": content,
                            "start_line": current_section["start_line"]
                        })
                
                # Start new section
                level = len(match.group(1))
                heading_text = match.group(2).strip()
                current_section = {
                    "heading": heading_text,
                    "heading_level": level,
                    "content_lines": [],
                    "start_line": i
                }
            else:
                current_section["content_lines"].append(line)

        # Don't forget the last section
        if current_section["content_lines"] or current_section["heading"]:
            content = "\n".join(current_section["content_lines"]).strip()
            sections.append({
                "heading": current_section["heading"],
                "heading_level": current_section["heading_level"],
                "content": content,
                "start_line": current_section["start_line"]
            })

        return sections

    def split_section_into_chunks(
        self, 
        section: Dict, 
        document_id: str,
        client_id: str,
        start_index: int
    ) -> Tuple[List[Dict], int]:
        """
        Split a section into token-aware chunks.
        
        Returns (chunks, next_index).
        """
        heading = section.get("heading")
        heading_level = section.get("heading_level", 0)
        content = section.get("content", "")
        
        # Combine heading with content for chunking
        full_text = f"{'#' * heading_level} {heading}\n\n{content}" if heading else content
        full_text = full_text.strip()
        
        if not full_text:
            return [], start_index

        chunks = []
        token_count = self.count_tokens(full_text)

        # If section fits in one chunk, return as is
        if token_count <= self.chunk_size:
            chunk_type = self.infer_chunk_type(heading, content)
            chunks.append({
                "chunk_id": f"c_{document_id}_{start_index}",
                "document_id": document_id,
                "client_id": client_id,
                "chunk_index": start_index,
                "text": full_text,
                "heading": heading,
                "heading_level": heading_level,
                "chunk_type": chunk_type,
                "token_count": token_count
            })
            return chunks, start_index + 1

        # Split into paragraphs first
        paragraphs = re.split(r"\n\s*\n", full_text)
        
        current_chunk_text = ""
        current_chunk_tokens = 0
        chunk_index = start_index

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            para_tokens = self.count_tokens(para)
            
            # If single paragraph is too large, split by sentences
            if para_tokens > self.chunk_size:
                # Save current chunk if any
                if current_chunk_text:
                    chunk_type = self.infer_chunk_type(heading, current_chunk_text)
                    chunks.append({
                        "chunk_id": f"c_{document_id}_{chunk_index}",
                        "document_id": document_id,
                        "client_id": client_id,
                        "chunk_index": chunk_index,
                        "text": current_chunk_text.strip(),
                        "heading": heading,
                        "heading_level": heading_level,
                        "chunk_type": chunk_type,
                        "token_count": current_chunk_tokens
                    })
                    chunk_index += 1
                    current_chunk_text = ""
                    current_chunk_tokens = 0
                
                # Split paragraph by sentences
                sentences = re.split(r"(?<=[.!?])\s+", para)
                for sentence in sentences:
                    sentence = sentence.strip()
                    if not sentence:
                        continue
                    
                    sent_tokens = self.count_tokens(sentence)
                    
                    if current_chunk_tokens + sent_tokens > self.chunk_size:
                        if current_chunk_text:
                            chunk_type = self.infer_chunk_type(heading, current_chunk_text)
                            chunks.append({
                                "chunk_id": f"c_{document_id}_{chunk_index}",
                                "document_id": document_id,
                                "client_id": client_id,
                                "chunk_index": chunk_index,
                                "text": current_chunk_text.strip(),
                                "heading": heading,
                                "heading_level": heading_level,
                                "chunk_type": chunk_type,
                                "token_count": current_chunk_tokens
                            })
                            chunk_index += 1
                        current_chunk_text = sentence + " "
                        current_chunk_tokens = sent_tokens
                    else:
                        current_chunk_text += sentence + " "
                        current_chunk_tokens += sent_tokens
            
            # Normal paragraph fits
            elif current_chunk_tokens + para_tokens > self.chunk_size:
                # Save current chunk
                if current_chunk_text:
                    chunk_type = self.infer_chunk_type(heading, current_chunk_text)
                    chunks.append({
                        "chunk_id": f"c_{document_id}_{chunk_index}",
                        "document_id": document_id,
                        "client_id": client_id,
                        "chunk_index": chunk_index,
                        "text": current_chunk_text.strip(),
                        "heading": heading,
                        "heading_level": heading_level,
                        "chunk_type": chunk_type,
                        "token_count": current_chunk_tokens
                    })
                    chunk_index += 1
                
                # Start new chunk with overlap
                overlap_text = self._get_overlap_text(current_chunk_text)
                current_chunk_text = overlap_text + para + "\n\n"
                current_chunk_tokens = self.count_tokens(current_chunk_text)
            else:
                current_chunk_text += para + "\n\n"
                current_chunk_tokens += para_tokens

        # Save final chunk
        if current_chunk_text.strip():
            chunk_type = self.infer_chunk_type(heading, current_chunk_text)
            chunks.append({
                "chunk_id": f"c_{document_id}_{chunk_index}",
                "document_id": document_id,
                "client_id": client_id,
                "chunk_index": chunk_index,
                "text": current_chunk_text.strip(),
                "heading": heading,
                "heading_level": heading_level,
                "chunk_type": chunk_type,
                "token_count": self.count_tokens(current_chunk_text)
            })
            chunk_index += 1

        return chunks, chunk_index

    def _get_overlap_text(self, text: str) -> str:
        """Get overlap text from end of previous chunk."""
        if not text or self.chunk_overlap <= 0:
            return ""
        
        # Get last N tokens worth of text
        words = text.split()
        overlap_words = []
        token_count = 0
        
        for word in reversed(words):
            word_tokens = self.count_tokens(word)
            if token_count + word_tokens > self.chunk_overlap:
                break
            overlap_words.insert(0, word)
            token_count += word_tokens
        
        return " ".join(overlap_words) + " " if overlap_words else ""

    def chunk_document(
        self, 
        text: str, 
        document_id: str, 
        client_id: str
    ) -> List[Dict]:
        """
        Chunk a document into semantic chunks.
        
        Args:
            text: Document text (markdown format preferred)
            document_id: Document identifier
            client_id: Client identifier
            
        Returns:
            List of chunk dictionaries ready for database storage
        """
        if not text or not text.strip():
            logger.warning(f"Empty document: {document_id}")
            return []

        logger.info(f"Chunking document {document_id} ({len(text)} chars)")

        # Parse into sections by headings
        sections = self.parse_headings(text)
        
        if not sections:
            # No headings found, treat entire text as one section
            sections = [{
                "heading": None,
                "heading_level": 0,
                "content": text,
                "start_line": 0
            }]

        # Chunk each section
        all_chunks = []
        chunk_index = 0
        
        for section in sections:
            section_chunks, chunk_index = self.split_section_into_chunks(
                section, document_id, client_id, chunk_index
            )
            all_chunks.extend(section_chunks)

        logger.info(f"Created {len(all_chunks)} chunks for document {document_id}")
        return all_chunks
