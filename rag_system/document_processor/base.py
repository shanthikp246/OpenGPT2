from abc import ABC, abstractmethod
from typing import List

class DocumentProcessor(ABC):
    @abstractmethod
    def process(self) -> List[str]: pass
