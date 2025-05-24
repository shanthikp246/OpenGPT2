import os
import json
from transformers import AutoTokenizer, AutoModelForQuestionAnswering, pipeline
from train.qa_finetuner import QAFineTuner
from qa_generator.generator_extractor import GeneratorExtractorQAGenerator
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
        self.status = "initializing"
        self.eval_results = None

    def initialize(self):
        os.makedirs(self.model_output_dir, exist_ok=True)
        blobstore = LocalBlobStore(self.documents_path)
        parser = PDFParser()

        # Only fine-tune if model doesn't already exist
        if not os.path.exists(self.model_path):
            print("🔄 Fine-tuning pipeline initiated...")
            self.status = "Generate QA pairs initiated"
            generator = GeneratorExtractorQAGenerator(blobstore, parser, self.qa_data_path)
            generator.generate_qa_pairs()
            self.status = "Generate QA pairs complete"

        try:
            finetuner = QAFineTuner(
                blobstore=blobstore,
                model_name="distilbert-base-cased",
                output_dir=self.model_path
            )
            self.status = "Fine tuning model..."
            finetuner.train(self.qa_data_path)
            self.status = "Evaluating model..."
    
            # Optional but recommended
            self.eval_results = finetuner.evaluate(self.qa_data_path)
            print(f"📊 Evaluation Results: {self.eval_results}")
        except Exception as e:
            print(f"🔥 Error fine-tuning model: {e}")
            raise


        # Load model and tokenizer
        print("📦 Loading fine-tuned model...")
        self.status = "Loading fine-tuned model..."
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForQuestionAnswering.from_pretrained(self.model_path)
        self.qa_pipeline = pipeline("question-answering", model=self.model, tokenizer=self.tokenizer)
        self.status = "Inference ready"
        
    def is_ready(self) -> bool:
        return self.qa_pipeline is not None

    def generate(self, question: str, context: str) -> tuple[str, float]:
        result = self.qa_pipeline(question=question, context=context)
        return result["answer"], result["score"]
    
    def get_status(self) -> str:
        return {"status": self.status}

