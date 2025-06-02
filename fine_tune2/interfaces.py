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

class IDocumentExtractor(ABC):
    @abstractmethod
    async def extract_text(self, file_content: bytes, file_extension: str) -> str:
        pass

class IQuestionGenerator(ABC):
    @abstractmethod
    async def generate_qa_pairs(self, context: str, doc_id: str) -> List[SQuADExample]:
        pass

class IStatusTracker(ABC):
    @abstractmethod
    async def update_status(self, task_id: str, status: GenerationStatus) -> None:
        pass
    
    @abstractmethod
    async def get_status(self, task_id: str) -> Optional[GenerationStatus]:
        pass