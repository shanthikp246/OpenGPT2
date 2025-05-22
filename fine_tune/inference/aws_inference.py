import os
import json
import tempfile
from transformers import AutoTokenizer, AutoModelForQuestionAnswering, pipeline
from train.qa_finetuner import QAFineTuner
from train.qa_data_generator import QAGenerator
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

        if not self._model_exists():
            print("🔄 Fine-tuning pipeline initiated with S3 backend...")
            generator = QAGenerator(blobstore=blobstore, parser=parser)
            qa_pairs = generator.generate()

            with tempfile.NamedTemporaryFile(mode='w+', delete=False) as f:
                json.dump(qa_pairs, f)
                qa_data_path = f.name

            # Save QA pairs to S3
            blobstore.write_file(self.qa_data_key, json.dumps(qa_pairs))

            # Fine-tune and push model to S3
            finetuner = QAFineTuner(
                blobstore=blobstore,
                model_name="distilbert-base-case_

