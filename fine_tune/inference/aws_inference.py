import os
from enum import Enum
from transformers import AutoTokenizer, AutoModelForQuestionAnswering, pipeline
from train.qa_finetuner import QAFineTuner
from qa_generator.generator_extractor import GeneratorExtractorQAGenerator
from blobstore.s3_blobstore import S3BlobStore
from parser.pdf_parser import PDFParser
from inference.base import BaseInference, InferenceStatus

class AwsInference(BaseInference):
    def __init__(self, s3_bucket: str, qa_data_path: str, model_output_dir: str):
        super().__init__(qa_data_path, model_output_dir)
        self.blobstore = S3BlobStore(s3_bucket, prefix="")

    def get_blobstore(self):
        return self.blobstore
