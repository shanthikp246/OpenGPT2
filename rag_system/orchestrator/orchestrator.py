from abc import ABC, abstractmethod

class RAGOrchestrator(ABC):
    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def query(self, query: str, top_k: int) -> str:
        pass
