# parser/base.py
from abc import ABC, abstractmethod

class DocumentParser(ABC):
    @abstractmethod
    def parse(self, file_bytes: bytes) -> str: pass

