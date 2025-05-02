from abc import ABC, abstractmethod

class LLMModel(ABC):
    @abstractmethod
    def generate(self, context: str, query: str) -> str: pass
