# parser/pdf_parser.py
import fitz  # PyMuPDF exposes itself as 'fitz'
from .base import DocumentParser

class PDFParser:
    def parse(self, file_bytes: bytes) -> str:
        """Extract text from PDF bytes."""
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text = "\n".join(page.get_text() for page in doc)
        return text

