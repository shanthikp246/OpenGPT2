import textwrap
from blobstore.base import BlobStore
from .base import DocumentProcessor
import fitz  # PyMuPDF
import os

class SimpleDocumentProcessor(DocumentProcessor):
    def __init__(self, blobstore: BlobStore, chunk_size=500):
        self.blobstore = blobstore
        self.chunk_size = chunk_size

    def process(self):
        chunks = []

        for file_path in self.blobstore.list_files():
            ext = os.path.splitext(file_path)[1].lower()

            if ext == ".txt":
                text = self.blobstore.read_file(file_path)
            elif ext == ".pdf":
                text = self._extract_text_from_pdf(file_path)
            else:
                print(f"⚠️ Skipping unsupported file type: {file_path}")
                continue

            wrapped = textwrap.wrap(text, self.chunk_size)
            for chunk in wrapped:
                chunks.append({"text": chunk, "source": file_path})

        return chunks

    def _extract_text_from_pdf(self, file_path):
        # Download from blobstore to local temp path
        local_pdf_path = f"/tmp/{os.path.basename(file_path)}"
        self.blobstore.download_file(file_path, local_pdf_path)

        text = ""
        try:
            with fitz.open(local_pdf_path) as doc:
                for page in doc:
                    text += page.get_text()
        finally:
            os.remove(local_pdf_path)

        return text
