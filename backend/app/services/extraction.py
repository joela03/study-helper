"""
Document text extraction service.
Extracts text from PDFs, PowerPoint slides, and Word/plain-text documents.
"""
import io
from pathlib import Path

from PyPDF2 import PdfReader
from docx import Document
from pptx import Presentation


# Suffixes that mean "this file is already a transcript", not audio to send
# through Whisper. Checked on upload so a pasted-in Panopto export is routed
# to the transcript path even if it arrives in the audio field.
PLAIN_TEXT_SUFFIXES = {".txt", ".md", ".markdown"}
WORD_SUFFIXES = {".docx"}
TRANSCRIPT_SUFFIXES = PLAIN_TEXT_SUFFIXES | WORD_SUFFIXES

# Legacy binary Word. python-docx cannot read these, and they must not fall
# through to Whisper, so they are rejected with an explanation instead.
LEGACY_WORD_SUFFIXES = {".doc"}


def extract_from_pdf(file_path: str) -> str:
    """Extract text from a PDF file."""
    reader = PdfReader(file_path)
    text_parts = []

    for page_num, page in enumerate(reader.pages, 1):
        page_text = page.extract_text()
        if page_text:
            text_parts.append(f"[Page {page_num}]\n{page_text.strip()}")

    return "\n\n".join(text_parts)


def extract_from_pptx(file_path: str) -> str:
    """Extract text from a PowerPoint file."""
    prs = Presentation(file_path)
    text_parts = []

    for slide_num, slide in enumerate(prs.slides, 1):
        slide_text = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                slide_text.append(shape.text.strip())

        if slide_text:
            text_parts.append(f"[Slide {slide_num}]\n" + "\n".join(slide_text))

    return "\n\n".join(text_parts)


def extract_from_docx(file_path: str) -> str:
    """Extract text from a Word (.docx) file, paragraphs and tables."""
    doc = Document(file_path)
    parts = [p.text.strip() for p in doc.paragraphs if p.text.strip()]

    for table in doc.tables:
        for row in table.rows:
            cells = [c.text.strip() for c in row.cells if c.text.strip()]
            if cells:
                parts.append(" | ".join(cells))

    return "\n\n".join(parts)


def is_transcript_file(filename: str | None) -> bool:
    """True if this filename looks like an already-made transcript."""
    if not filename:
        return False
    return Path(filename).suffix.lower() in TRANSCRIPT_SUFFIXES


def is_legacy_word_file(filename: str | None) -> bool:
    """True for .doc, which cannot be read and must not reach Whisper."""
    if not filename:
        return False
    return Path(filename).suffix.lower() in LEGACY_WORD_SUFFIXES


def extract_transcript_text(file_path: str) -> str:
    """
    Read an already-made transcript out of a text or Word file.
    Supports: TXT, MD, MARKDOWN, DOCX
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix in PLAIN_TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="replace")
    elif suffix in WORD_SUFFIXES:
        return extract_from_docx(file_path)
    else:
        raise ValueError(f"Not a transcript format: {suffix}")


def extract_document_text(file_path: str) -> str:
    """
    Extract text from a document based on file extension.
    Supports: PDF, PPTX, PPT, DOCX, TXT, MD
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_from_pdf(file_path)
    elif suffix in (".pptx", ".ppt"):
        return extract_from_pptx(file_path)
    elif suffix in TRANSCRIPT_SUFFIXES:
        return extract_transcript_text(file_path)
    else:
        raise ValueError(f"Unsupported document format: {suffix}")
