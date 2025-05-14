# parser/pdf_parser.py
import fitz

class PDFParser(DocumentParser):
    def parse(self, file_path: str) -> str:
        text = ""
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        return text

