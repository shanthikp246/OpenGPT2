import os
import json
import tempfile
from transformers import AutoTokenizer, AutoModelForQuestionAnswering, pipeline
from train.qa_finetuner import QAFineTuner
from qa_generator.generator_extractor import GeneratorExtractorQAGenerator
from blobstore.s3_blobstore import S3BlobStore
from parser.pdf_parser import PDFParser
from inference.inference import Inference

class AwsInference(Inference):
    def __init__(self, s3_bucket: str, qa_data_path: str, model_output_dir: str):
        self.s3_bucket = s3_bucket
        self.qa_data_path = qa_data_path
        self.model_path = model_output_dir
        self.model = None
        self.eval_results = None
        self.qa_pipeline = None
        self.status = "initializing"

    def initialize(self):
        blobstore = S3BlobStore(self.s3_bucket, prefix=self.documents_prefix)
        parser = PDFParser()

        # Only fine-tune if model doesn't already exist
        if not os.path.exists(self.model_path):
            print("🔄 Fine-tuning pipeline initiated...")
            self.status = "Generate QA pairsinitiated"
            generator = GeneratorExtractorQAGenerator(blobstore, parser, self.qa_data_path)
            generator.generate_qa_pairs()
            self.status = "Generate QA pairs complete"

        try:
            finetuner = QAFineTuner(
                blobstore=blobstore,
                model_name="distilbert-base-cased",
                output_dir=self.model_path
            )
            self.status = "Fine tuning model.."
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
        self.tokenizer = AutoTokenizer.from_pretrained(self.model_path)
        self.model = AutoModelForQuestionAnswering.from_pretrained(self.model_path)
        self.qa_pipeline = pipeline("question-answering", model=self.model, tokenizer=self.tokenizer)
        self.status = "Inference ready"

    def is_ready(self) -> bool:
        return self.qa_pipeline is not None

    def generate(self, question: str, context: str) -> tuple[str, float]:
        result = self.qa_pipeline(question=question, context=context)
        return result["answer"], result["score"]
    
    def get_status(self) -> dict:
        return {"status": self.status}



