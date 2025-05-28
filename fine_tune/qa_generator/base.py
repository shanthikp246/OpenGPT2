# qa_generator/base.py

from abc import ABC, abstractmethod
from typing import List, Dict

class QAGenerator(ABC):
    @abstractmethod
    def generate_qa_pairs(self) -> List[Dict]:
        """
        Generate question-answer pairs from documents and return them in SQuAD format.
        """
        pass

