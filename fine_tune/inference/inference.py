from abc import ABC, abstractmethod

class Inference(ABC):
    @abstractmethod
    def initialize(self):
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        pass

    @abstractmethod
    def generate(self, question: str, context: str) -> tuple[str, float]:
        pass

    @abstractmethod
    def get_status(self) -> dict:
        pass

