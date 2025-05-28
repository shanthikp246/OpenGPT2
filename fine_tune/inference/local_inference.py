import os
import json
from transformers import AutoTokenizer, AutoModelForQuestionAnswering, pipeline
from train.qa_finetuner import QAFineTuner
from qa_generator.generator_extractor import GeneratorExtractorQAGenerator
from blobstore.local_blobstore import LocalBlobStore
from parser.pdf_parser import PDFParser
from inference.base import BaseInference, InferenceStatus

class LocalInference(BaseInference):
    def __init__(self, documents_path: str, qa_data_path: str, model_output_dir: str):
        super().__init__(qa_data_path, model_output_dir)
        self.blobstore = LocalBlobStore(documents_path)

    def get_blobstore(self):
        return self.blobstore




