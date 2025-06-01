from abc import ABC, abstractmethod
from enum import Enum
from transformers import AutoTokenizer, AutoModelForQuestionAnswering, pipeline
from train.qa_finetuner import QAFineTuner
from qa_generator.generator_extractor import GeneratorExtractorQAGenerator
from parser.pdf_parser import PDFParser

class BaseInference(ABC):
    def __init__(self, qa_data_path, model_output_dir):
        self.qa_data_path = qa_data_path
        self.model_path = model_output_dir
        self.model = None
        self.eval_results = None
        self.qa_pipeline = None
        self.tokenizer = None
        self.status = InferenceStatus.INITIALIZING
        self.last_error: str | None = None
    
    @abstractmethod
    def get_blobstore(self):
        pass

    def initialize(self):
        parser = PDFParser()
        blobstore = self.get_blobstore()

        try:
            self.last_error = f"Checking Model output directory: {self.model_path}"
            if not blobstore.exists(self.model_path):
                self.last_error = "🔄 Fine-tuning pipeline initiated..."
                self.status = InferenceStatus.GENERATING_QA
                generator = GeneratorExtractorQAGenerator(blobstore, parser, self.qa_data_path)
                generator.generate_qa_pairs()

                self.status = InferenceStatus.FINE_TUNING
                finetuner = QAFineTuner(
                    blobstore=blobstore,
                    model_name="distilbert-base-cased",
                    output_dir=self.model_path
                )
                finetuner.train(self.qa_data_path)

                self.status = InferenceStatus.EVALUATING
                self.eval_results = finetuner.evaluate(self.qa_data_path)
                print(f"📊 Evaluation Results: {self.eval_results}")

            self.status = InferenceStatus.LOADING_MODEL
            self.last_error = "📦 Loading fine-tuned model..."
            self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
            self.model = AutoModelForQuestionAnswering.from_pretrained(self.model_path)
            self.qa_pipeline = pipeline("question-answering", model=self.model, tokenizer=self.tokenizer)

            self.status = InferenceStatus.READY

        except Exception as e:
            self.last_error = str(e)
            self.status = InferenceStatus.ERROR
            print(f"🔥 Error during initialization: {self.last_error}")
            raise

    def is_ready(self) -> bool:
        return self.status == InferenceStatus.READY

    def generate(self, question: str, context: str) -> tuple[str, float]:
        if not self.qa_pipeline:
            raise RuntimeError("Inference model not loaded.")
        result = self.qa_pipeline(question=question, context=context)
        return result["answer"], result["score"]

    def get_status(self) -> dict:
        return {
            "status": self.status,
            "error": self.last_error if self.status == InferenceStatus.ERROR else None,
            "eval_results": self.eval_results if self.eval_results else None
        }

class InferenceStatus(str, Enum):
    INITIALIZING = "initializing"
    GENERATING_QA = "generating_qa_pairs"
    FINE_TUNING = "fine_tuning"
    EVALUATING = "evaluating"
    LOADING_MODEL = "loading_model"
    READY = "inference_ready"
    ERROR = "error"

