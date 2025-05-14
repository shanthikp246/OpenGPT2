from abc import ABC, abstractmethod
from typing import List

class VectorDB(ABC):
    @abstractmethod
    def build_index(self, embeddings: List[List[float]], documents: List[str]): pass

    @abstractmethod
    def query(self, embedding: List[float], k: int) -> List[str]: pass

    @abstractmethod
    def load(self): pass
