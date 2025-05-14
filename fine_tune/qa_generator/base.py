# qa_generator/base.py
from abc import ABC, abstractmethod

class QAGenerator(ABC):
    @abstractmethod
    def generate(self, text: str) -> list[dict]: pass

