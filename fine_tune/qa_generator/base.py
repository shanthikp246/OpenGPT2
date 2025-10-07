# qa_generator/base.py

from abc import ABC, abstractmethod
from typing import Any, Dict

class QAGenerator(ABC):
    @abstractmethod
    def generate_qa_pairs(self) -> Dict[str, Any]:
        """Generate question-answer pairs and return a SQuAD-formatted dataset."""
        pass

