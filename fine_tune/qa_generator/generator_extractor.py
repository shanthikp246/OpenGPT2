# qa_generator/generator_extractor.py

import os
import uuid
import json
import textwrap
from typing import List, Dict
from transformers import pipeline
from qa_generator.base import QAGenerator
from blobstore.base import BlobStore
from parser.base import DocumentParser

class GeneratorExtractorQAGenerator(QAGenerator):
    def __init__(
        self,
        blobstore: BlobStore,
        parser: DocumentParser,
        output_path: str,
        chunk_size: int = 500,
        max_questions_per_chunk: int = 3,
    ):
        self.blobstore = blobstore
        self.parser = parser
        self.output_path = output_path
        self.chunk_size = chunk_size
        self.max_questions_per_chunk = max_questions_per_chunk

        self.question_generator = pipeline("text2text-generation", model="google/flan-t5-large", max_length=64)
        self.answer_extractor = pipeline("question-answering", model="distilbert-base-cased-distilled-squad")

    def split_text(self, text: str) -> List[str]:
        return textwrap.wrap(text, self.chunk_size)

    def generate_qa_pairs(self) -> List[Dict]:
        qa_dataset = []

        for file_path in self.blobstore.list_files():
            print(f"Processing file: {file_path}")
            file_bytes = self.blobstore.read_file(file_path)
            pdf_text = self.parser.parse(file_bytes)
            chunks = self.split_text(pdf_text)

            for chunk in chunks:
                prompt = f"Generate {self.max_questions_per_chunk} questions from the following text:\n{chunk}"
                questions_output = self.question_generator(prompt, num_return_sequences=1)[0]['generated_text']

                questions = [q.strip() for q in questions_output.split('\n') if q.strip()]
                questions = questions[:self.max_questions_per_chunk]

            for question in questions:
                answer = self.answer_extractor(question=question, context=chunk)
                qa_dataset.append({
                    "id": str(uuid.uuid4()),
                    "title": os.path.basename(file_path),
                    "context": chunk,
                    "question": question,
                    "answers": {
                        "text": [answer["answer"]],
                        "answer_start": [chunk.find(answer["answer"])]
                    }
                })

        self.blobstore.write_file(self.output_path, json.dumps({"data": qa_dataset}, indent=2))
        print(f"Saved {len(qa_dataset)} QA pairs to {self.output_path}")
        return qa_dataset

