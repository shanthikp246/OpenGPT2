import os
import json
from transformers import AutoTokenizer, AutoModelForQuestionAnswering, pipeline
from train.qa_finetuner import QAFineTuner
from train.qa_data_generator import QAGenerator
from blobstore.local_blobstore import LocalBlobStore
from parser.pdf_parser import PDFParser
from inference.inference import Inference

class LocalInference(Inference):
    def __init__(self, documents_path: str, qa_data_path: str, model_output_dir: str):
        self.documents_path = documents_path
        self.qa_data_path = qa_data_path
        self.model_output_dir = model_output_dir
        self.model_path = os.path.join(model_output_dir, "finetuned-model")
        self.model = None
        self.qa_pipeline = None

    def initialize(self):
        os.makedirs(self.model_output_dir, exist_ok=True)
        blobstore = LocalBlobStore(self.documents_path)
        parser = PDFParser()

        # Only fine-tune if model doesn't already exist
        if not os.path.exists(self.model_path):
            print("🔄 Fine-tuning pipeline initiated...")
            generator = QAGenerator(blobstore=blobstore, parser=parser)
            qa_pairs = generator.generate()
            with open(self.qa_data_path, "w") as f:
                json.dump(qa_pairs, f)

            finetuner = QAFineTuner(
                model_name="distilbert-base-cased",
                output_dir=self.model_path
            )
            finetuner.train(self.qa_data_path)
            finetuner.evaluate(self.qa_data_path)

        # Load model and tokenizer
        print("📦 Loading fine-tuned model...")
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForQuestionAnswering.from_pretrained(self.model_path)
        self.qa_pipeline = pipeline("question-answering", model=self.model, tokenizer=self.tokenizer)

    def is_ready(self) -> bool:
        return self.qa_pipeline is not None

    def generate(self, question: str, context: str) -> tuple[str, float]:
        result = self.qa_pipeline(question=question, context=context)
        return result["answer"], result["score"]

