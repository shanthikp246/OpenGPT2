# interfaces.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, AsyncGenerator
from dataclasses import dataclass
import asyncio

@dataclass
class FileInfo:
    key: str
    size: int
    last_modified: str

@dataclass
class SQuADExample:
    context: str
    question: str
    answer: str
    answer_start: int
    id: str

@dataclass
class GenerationStatus:
    task_id: str
    bucket_name: str
    status: str  # "running", "completed", "failed", "pending"
    total_files: int
    processed_files: int
    generated_examples: int
    error_message: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

class IBlobStore(ABC):
    @abstractmethod
    async def list_files(self, bucket: str, prefix: str = "") -> List[FileInfo]:
        pass
    
    @abstractmethod
    async def read_file(self, bucket: str, key: str) -> bytes:
        pass
    
    @abstractmethod
    async def write_file(self, bucket: str, key: str, content: bytes) -> None:
        pass
    
    @abstractmethod
    async def file_exists(self, bucket: str, key: str) -> bool:
        pass

class IStatusTracker(ABC):
    @abstractmethod
    async def update_status(self, task_id: str, status: GenerationStatus) -> None:
        pass
    
    @abstractmethod
    async def get_status(self, task_id: str) -> Optional[GenerationStatus]:
        pass

from abc import ABC, abstractmethod
from typing import List, Dict

# --- Updated Interface Definitions ---

class IDocumentExtractor(ABC):
    @abstractmethod
    async def extract_sections(self, file_content: bytes, file_extension: str) -> List[Dict]:
        """
        Extracts both text blocks and tables from a document.

        Returns a list of sections with:
        - type: 'text' or 'table'
        - content: extracted text
        - page: page number (optional)
        """
        pass


class IQAGenerator(ABC):
    @abstractmethod
    async def generate_qa_pairs(self, sections: List[Dict], doc_id: str) -> List["SQuADExample"]:
        """
        Generates QA pairs from structured sections of text/tables.
        Each section has 'type', 'content', and optionally 'page'.
        """
        pass

    @abstractmethod
    def status(self) -> bool:
        pass

    @abstractmethod
    async def init_models(self):
        pass
