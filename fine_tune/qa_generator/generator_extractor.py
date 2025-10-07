# qa_generator/generator_extractor.py

import os
import uuid
import json
import textwrap
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from transformers import pipeline

from ..blobstore.base import BlobStore
from ..parser.base import DocumentParser
from .base import QAGenerator

class GeneratorExtractorQAGenerator(QAGenerator):
    def __init__(
        self,
        blobstore: BlobStore,
        parser: DocumentParser,
        output_path: str,
        chunk_size: int = 500,
        max_questions_per_chunk: int = 3,
        source_prefix: Optional[str] = None,
    ):
        self.blobstore = blobstore
        self.parser = parser
        self.output_path = output_path
        self.chunk_size = chunk_size
        self.max_questions_per_chunk = max_questions_per_chunk
        self.source_prefix = source_prefix.strip("/") if source_prefix else None

        self.question_generator = pipeline("text2text-generation", model="google/flan-t5-large", max_length=64)
        self.answer_extractor = pipeline("question-answering", model="distilbert-base-cased-distilled-squad")

    def split_text(self, text: str) -> List[str]:
        """Split the input text into reasonably-sized chunks.

        The default implementation keeps chunks roughly under ``self.chunk_size`` characters
        while avoiding breaking words mid-sentence. Empty chunks are filtered out so we never
        generate bogus questions.
        """

        return [chunk for chunk in textwrap.wrap(text, self.chunk_size) if chunk.strip()]

    def _iter_source_documents(self) -> Iterable[str]:
        allowed_extensions = {".pdf", ".txt"}
        for file_path in self.blobstore.list_files():
            if self.source_prefix and not file_path.startswith(self.source_prefix):
                continue
            if Path(file_path).suffix.lower() not in allowed_extensions:
                continue
            yield file_path

    def _normalise_answers(self, answer_text: str, context: str) -> Tuple[str, int]:
        """Return the answer text and its start index if found in the context."""

        answer_text = answer_text.strip()
        answer_start = context.find(answer_text) if answer_text else -1
        return answer_text, answer_start

    def generate_qa_pairs(self) -> Dict[str, Any]:
        """Generate a full SQuAD-formatted dataset from the configured blobstore.

        The returned structure complies with the official SQuAD v1.1 schema so that downstream
        tooling (including Hugging Face datasets and metrics) can consume the results without
        additional adapters.
        """

        dataset: Dict[str, Any] = {"version": "1.1", "data": []}
        total_examples = 0

        for file_path in self._iter_source_documents():
            print(f"Processing file: {file_path}")
            file_bytes = self.blobstore.read_file(file_path)
            document_text = self.parser.parse(file_bytes)
            chunks = self.split_text(document_text)

            article = {
                "title": os.path.basename(file_path) or "untitled",
                "paragraphs": [],
            }

            for chunk in chunks:
                prompt = (
                    "Generate up to "
                    f"{self.max_questions_per_chunk} questions from the following text:\n{chunk}"
                )
                generations = self.question_generator(
                    prompt,
                    num_return_sequences=1,
                )[0]["generated_text"]

                questions = [q.strip() for q in generations.split("\n") if q.strip()]
                questions = questions[: self.max_questions_per_chunk]

                qas = []
                for question in questions:
                    answer = self.answer_extractor(question=question, context=chunk)
                    answer_text, answer_start = self._normalise_answers(answer["answer"], chunk)

                    if not answer_text:
                        continue

                    qas.append(
                        {
                            "id": str(uuid.uuid4()),
                            "question": question,
                            "is_impossible": False,
                            "answers": [
                                {
                                    "text": answer_text,
                                    "answer_start": answer_start,
                                }
                            ],
                        }
                    )

                if qas:
                    article["paragraphs"].append({"context": chunk, "qas": qas})
                    total_examples += len(qas)

            if article["paragraphs"]:
                dataset["data"].append(article)

        documents_processed = len(dataset["data"])
        dataset["metadata"] = {
            "documents": documents_processed,
            "total_examples": total_examples,
        }

        print(f"Generated {total_examples} QA pairs across {documents_processed} documents")
        self.blobstore.write_file(self.output_path, json.dumps(dataset, indent=2))
        print(f"Saved dataset to {self.output_path}")
        return dataset

