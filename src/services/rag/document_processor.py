"""
Document Processor Service

This module handles the extraction and chunking of various document formats
for ingestion into the RAG system.
"""

import hashlib
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Iterator, List, Optional, Sequence
from uuid import NAMESPACE_URL, uuid5

import PyPDF2
from docx import Document as DocxDocument

logger = logging.getLogger(__name__)


class DocumentType(str, Enum):
    """Supported document types."""

    PDF = "pdf"
    DOCX = "docx"
    MARKDOWN = "markdown"
    TEXT = "text"


# Chunking constants
DEFAULT_TARGET_WORDS = 180
DEFAULT_MAX_WORDS = 240
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")
TOKEN_PATTERN = re.compile(r"[A-Za-z0-9']+")


@dataclass(frozen=True)
class DocumentChunk:
    """Represents a single chunk of a document."""

    text: str
    section: str
    chunk_index: int
    chunk_count: int
    source: str
    checksum: str
    namespace: Optional[str]
    point_id: str

    def to_payload(self) -> dict:
        """Convert chunk to payload for vector database ingestion."""
        payload = {
            "id": self.point_id,
            "text": self.text,
            "metadata": {
                "source": self.source,
                "section": self.section,
                "chunk_index": self.chunk_index,
                "chunks_total": self.chunk_count,
                "checksum": self.checksum,
                "word_count": len(_tokenize(self.text)),
            },
        }
        if self.namespace:
            payload["namespace"] = self.namespace
        return payload


def _tokenize(text: str) -> List[str]:
    """Tokenize text into words."""
    return TOKEN_PATTERN.findall(text.lower())


def _sliding_chunks(items: Sequence[str], target_words: int, max_words: int) -> Iterator[List[str]]:
    """Create sliding chunks from paragraphs based on word count."""
    chunk: List[str] = []
    word_count = 0

    for item in items:
        tokens = _tokenize(item)
        if not tokens:
            continue

        prospective_count = word_count + len(tokens)
        if chunk and prospective_count > max_words:
            yield chunk
            chunk = []
            word_count = 0

        chunk.append(item)
        word_count += len(tokens)

        if word_count >= target_words:
            yield chunk
            chunk = []
            word_count = 0

    if chunk:
        yield chunk


def _parse_sections(text: str) -> Iterator[tuple[str, List[str]]]:
    """Parse markdown-style sections from text."""
    current_title = "Overview"
    buffer: List[str] = []

    for line in text.splitlines():
        heading_match = HEADING_PATTERN.match(line.strip())
        if heading_match:
            if buffer:
                yield current_title, buffer
            level = len(heading_match.group(1))
            title = heading_match.group(2).strip()
            current_title = title or f"Untitled H{level}"
            buffer = []
        else:
            buffer.append(line)

    if buffer:
        yield current_title, buffer


def _section_paragraphs(lines: List[str]) -> List[str]:
    """Convert lines into paragraphs."""
    paragraphs: List[str] = []
    current: List[str] = []

    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current:
                paragraphs.append("\n".join(current).strip())
                current = []
            continue
        current.append(line.rstrip())

    if current:
        paragraphs.append("\n".join(current).strip())

    return [p for p in paragraphs if p]


def extract_text_from_pdf(file_path: Path) -> str:
    """Extract text from a PDF file."""
    try:
        text_parts = []
        with open(file_path, "rb") as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page_num, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
                except Exception as e:
                    logger.warning(f"Failed to extract text from page {page_num}: {e}")

        return "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"Failed to extract text from PDF {file_path}: {e}")
        raise ValueError(f"Failed to extract text from PDF: {e}")


def extract_text_from_docx(file_path: Path) -> str:
    """Extract text from a DOCX file."""
    try:
        doc = DocxDocument(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        return "\n\n".join(paragraphs)
    except Exception as e:
        logger.error(f"Failed to extract text from DOCX {file_path}: {e}")
        raise ValueError(f"Failed to extract text from DOCX: {e}")


def extract_text_from_file(file_path: Path, file_type: DocumentType) -> str:
    """Extract text from a file based on its type."""
    if file_type == DocumentType.PDF:
        return extract_text_from_pdf(file_path)
    elif file_type == DocumentType.DOCX:
        return extract_text_from_docx(file_path)
    elif file_type in (DocumentType.MARKDOWN, DocumentType.TEXT):
        return file_path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported document type: {file_type}")


def chunk_document(
    file_path: Path,
    *,
    namespace: Optional[str] = None,
    target_words: int = DEFAULT_TARGET_WORDS,
    max_words: int = DEFAULT_MAX_WORDS,
    file_type: Optional[DocumentType] = None,
) -> List[DocumentChunk]:
    """
    Chunk a document into smaller pieces for ingestion.

    Args:
        file_path: Path to the document file
        namespace: Optional namespace for the chunks
        target_words: Target words per chunk
        max_words: Maximum words per chunk
        file_type: Document type (auto-detected if not provided)

    Returns:
        List of DocumentChunk objects
    """
    # Auto-detect file type if not provided
    if file_type is None:
        extension = file_path.suffix.lower()
        type_mapping = {
            ".pdf": DocumentType.PDF,
            ".docx": DocumentType.DOCX,
            ".doc": DocumentType.DOCX,
            ".md": DocumentType.MARKDOWN,
            ".txt": DocumentType.TEXT,
        }
        file_type = type_mapping.get(extension)
        if file_type is None:
            raise ValueError(f"Unsupported file extension: {extension}")

    # Extract text
    text = extract_text_from_file(file_path, file_type)
    if not text.strip():
        raise ValueError(f"Document {file_path} is empty")

    chunks: List[DocumentChunk] = []
    seen_checksums: set[str] = set()

    # Chunk the text
    for section_title, lines in _parse_sections(text):
        paragraphs = _section_paragraphs(lines)
        if not paragraphs:
            continue

        merged_chunks = list(_sliding_chunks(paragraphs, target_words, max_words))
        total = len(merged_chunks) or 1

        for index, chunk_items in enumerate(merged_chunks or [paragraphs]):
            body = "\n\n".join(chunk_items).strip()
            enriched_text = f"{section_title}\n\n{body}" if section_title else body
            checksum = hashlib.sha256(enriched_text.encode("utf-8")).hexdigest()

            # Skip duplicates
            if checksum in seen_checksums:
                continue
            seen_checksums.add(checksum)

            point_id = str(uuid5(NAMESPACE_URL, checksum))
            chunks.append(
                DocumentChunk(
                    text=enriched_text,
                    section=section_title or "General",
                    chunk_index=index,
                    chunk_count=total,
                    source=file_path.name,
                    checksum=checksum,
                    namespace=namespace,
                    point_id=point_id,
                )
            )

    if not chunks:
        raise ValueError(f"No chunks generated from document {file_path}")

    return chunks


def process_uploaded_file(
    filename: str,
    content: bytes,
    *,
    namespace: Optional[str] = None,
    target_words: int = DEFAULT_TARGET_WORDS,
    max_words: int = DEFAULT_MAX_WORDS,
) -> tuple[List[DocumentChunk], DocumentType]:
    """
    Process an uploaded file and return chunks.

    Args:
        filename: Original filename
        content: File content as bytes
        namespace: Optional namespace for the chunks
        target_words: Target words per chunk
        max_words: Maximum words per chunk

    Returns:
        Tuple of (chunks, file_type)
    """
    import tempfile
    from pathlib import Path

    # Determine file type from extension
    extension = Path(filename).suffix.lower()
    type_mapping = {
        ".pdf": DocumentType.PDF,
        ".docx": DocumentType.DOCX,
        ".doc": DocumentType.DOCX,
        ".md": DocumentType.MARKDOWN,
        ".txt": DocumentType.TEXT,
    }
    file_type = type_mapping.get(extension)
    if file_type is None:
        raise ValueError(f"Unsupported file type: {extension}")

    # Write to temp file and process
    with tempfile.NamedTemporaryFile(suffix=extension, delete=False) as tmp_file:
        tmp_file.write(content)
        tmp_path = Path(tmp_file.name)

    try:
        chunks = chunk_document(
            tmp_path,
            namespace=namespace,
            target_words=target_words,
            max_words=max_words,
            file_type=file_type,
        )
        return chunks, file_type
    finally:
        # Clean up temp file
        tmp_path.unlink(missing_ok=True)
