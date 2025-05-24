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
    def __init__(self, s3_bucket: str, documents_prefix: str, qa_data_key: str, model_prefix: str):
        self.s3_bucket = s3_bucket
        self.documents_prefix = documents_prefix
        self.qa_data_key = qa_data_key
        self.model_prefix = model_prefix
        self.model_path = tempfile.mkdtemp()
        self.model = None
        self.qa_pipeline = None

    def initialize(self):
        blobstore = S3BlobStore(self.s3_bucket, prefix=self.documents_prefix)
        parser = PDFParser()

        # Only fine-tune if model doesn't already exist
        if not os.path.exists(self.model_path):
            print("🔄 Fine-tuning pipeline initiated...")
            generator = GeneratorExtractorQAGenerator(blobstore, parser, self.qa_data_path)
            generator.generate_qa_pairs()

        try:
            finetuner = QAFineTuner(
                blobstore=blobstore,
                model_name="distilbert-base-cased",
                output_dir=self.model_path
            )
            finetuner.train(self.qa_data_path)
    
            # Optional but recommended
            eval_results = finetuner.evaluate(self.qa_data_path)
            print(f"📊 Evaluation Results: {eval_results}")
        except Exception as e:
            print(f"🔥 Error fine-tuning model: {e}")
            raise

