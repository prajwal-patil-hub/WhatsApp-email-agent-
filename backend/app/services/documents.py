"""Document text extraction and chunking — Phase 4.

Supports PDF (pypdf), DOCX (python-docx), and plain text/Markdown.
Chunking: paragraph-aware splitter with overlap, sized for embedding models.
"""

import hashlib
import io

from app.core.logging import get_logger

logger = get_logger(__name__)

CHUNK_SIZE = 1200
CHUNK_OVERLAP = 200

SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".txt", ".md", ".markdown")


def content_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_text(data: bytes, filename: str) -> str:
    """Extract plain text from a document. Raises ValueError on unsupported type."""
    name = filename.lower()

    if name.endswith(".pdf"):
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages)

    if name.endswith(".docx"):
        import docx

        document = docx.Document(io.BytesIO(data))
        return "\n\n".join(p.text for p in document.paragraphs if p.text.strip())

    if name.endswith((".txt", ".md", ".markdown")):
        return data.decode("utf-8", errors="replace")

    raise ValueError(
        f"Unsupported file type: {filename}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
    )


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks, preferring paragraph boundaries."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""

    for para in paragraphs:
        # Hard-split paragraphs that alone exceed the chunk size
        while len(para) > chunk_size:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(para[:chunk_size])
            para = para[chunk_size - overlap :]

        if len(current) + len(para) + 2 <= chunk_size:
            current = f"{current}\n\n{para}" if current else para
        else:
            chunks.append(current)
            # Overlap: carry the tail of the previous chunk into the next
            tail = current[-overlap:] if overlap and len(current) > overlap else ""
            current = f"{tail}\n\n{para}" if tail else para

    if current:
        chunks.append(current)
    return chunks
