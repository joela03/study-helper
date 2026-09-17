"""
Document text extraction service.
Extracts text from PDFs and PowerPoint slides.
"""
import io
from pathlib import Path

from PyPDF2 import PdfReader
from pptx import Presentation


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


def extract_document_text(file_path: str) -> str:
    """
    Extract text from a document based on file extension.
    Supports: PDF, PPTX, PPT, TXT
    """
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        return extract_from_pdf(file_path)
    elif suffix in (".pptx", ".ppt"):
        return extract_from_pptx(file_path)
    elif suffix == ".txt":
        return path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported document format: {suffix}")
