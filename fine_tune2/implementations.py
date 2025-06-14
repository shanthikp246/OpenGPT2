# implementations.py
import boto3
import json
import re
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from botocore.exceptions import ClientError
import fitz  # PyMuPDF
from pdfminer.high_level import extract_text
import asyncio
import logging
from transformers import pipeline, AutoTokenizer, AutoModelForSeq2SeqLM, AutoModelForQuestionAnswering
import torch
import os
import textwrap
from typing import List, Dict
import psutil


from interfaces import *

logger = logging.getLogger(__name__)

class S3BlobStore(IBlobStore):
    def __init__(self, region_name: str = "us-west-2"):
        self.s3_client = boto3.client('s3', region_name=region_name)
    
    async def list_files(self, bucket: str, prefix: str = "") -> List[FileInfo]:
        try:
            response = self.s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)
            files = []
            for obj in response.get('Contents', []):
                files.append(FileInfo(
                    key=obj['Key'],
                    size=obj['Size'],
                    last_modified=obj['LastModified'].isoformat()
                ))
            return files
        except ClientError as e:
            logger.error(f"Error listing files in bucket {bucket}: {e}")
            raise
    
    async def read_file(self, bucket: str, key: str) -> bytes:
        try:
            response = self.s3_client.get_object(Bucket=bucket, Key=key)
            return response['Body'].read()
        except ClientError as e:
            logger.error(f"Error reading file {key} from bucket {bucket}: {e}")
            raise
    
    async def write_file(self, bucket: str, key: str, content: bytes) -> None:
        try:
            self.s3_client.put_object(Bucket=bucket, Key=key, Body=content)
        except ClientError as e:
            logger.error(f"Error writing file {key} to bucket {bucket}: {e}")
            raise
    
    async def file_exists(self, bucket: str, key: str) -> bool:
        try:
            self.s3_client.head_object(Bucket=bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return False
            raise

class DocumentExtractor(IDocumentExtractor):
    async def extract_text(self, file_content: bytes, file_extension: str) -> str:
        try:
            if file_extension.lower() == '.pdf':
                return await self._extract_pdf_text(file_content)
            elif file_extension.lower() == '.txt':
                return file_content.decode('utf-8')
            else:
                logger.warning(f"Unsupported file extension: {file_extension}")
                return ""
        except Exception as e:
            logger.error(f"Error extracting text from {file_extension} file: {e}")
            return ""
    
    async def _extract_pdf_text(self, pdf_content: bytes) -> str:
        try:
            # Use PyMuPDF for better text extraction
            doc = fitz.open(stream=pdf_content, filetype="pdf")
            text = ""
            for page in doc:
                text += page.get_text()
            doc.close()
            return text
        except Exception as e:
            logger.error(f"Error extracting PDF text with PyMuPDF: {e}")
            # Fallback to pdfminer
            try:
                return extract_text(pdf_content)
            except Exception as e2:
                logger.error(f"Error extracting PDF text with pdfminer: {e2}")
                return ""


class InMemoryStatusTracker(IStatusTracker):
    def __init__(self):
        self.statuses: Dict[str, GenerationStatus] = {}
    
    async def update_status(self, task_id: str, status: GenerationStatus) -> None:
        self.statuses[task_id] = status
    
    async def get_status(self, task_id: str) -> Optional[GenerationStatus]:
        return self.statuses.get(task_id)
    

class PdfPlumberExtractor(IDocumentExtractor):

    async def extract_text(self, file_content: bytes, file_extension: str) -> str:
        import io
        text_output = []
        import pdfplumber

        with pdfplumber.open(io.BytesIO(file_content)) as pdf:
            for page in pdf.pages:
                # Extract plain text
                page_text = page.extract_text() or ""

                # Extract tables and convert to text
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        for row in table:
                            page_text += "\n" + "\t".join(cell if cell else "" for cell in row)

                text_output.append(page_text.strip())

        return "\n\n".join(text_output).strip()

class GeneratorExtractorQAGenerator(IQAGenerator):
    def __init__(self, chunk_size: int = 512, max_questions_per_chunk: int = 5):
        self.max_questions_per_chunk = max_questions_per_chunk
        self.initialized = False
        self.question_generator = None
        self.answer_extractor = None
        #model="google/flan-t5-large",
        self.question_model = "google/flan-t5-base"
        #self.answer_model = "distilbert-base-uncased"
        self.answer_model = "distilbert-base-cased-distilled-squad"
        self.chunk_size = chunk_size
       

    async def init_models(self):
        if self.initialized:
            return

        logger.info("Initializing QA generator models...")
        loop = asyncio.get_event_loop()

        # Load the models in a thread-safe background executor
        self.question_generator = await loop.run_in_executor(
            None,
            lambda: pipeline(
                "text2text-generation",
                
                 model=self.question_model,
                max_length=64,
                device=0 if torch.cuda.is_available() else -1
            )
        )

        self.answer_extractor = await loop.run_in_executor(
            None,
            lambda: pipeline(
                "question-answering",
                
                model=self.answer_model,
                device=0 if torch.cuda.is_available() else -1
            )
        )

        tokenizer_q = AutoTokenizer.from_pretrained(self.question_model)
        tokenizer_a = AutoTokenizer.from_pretrained(self.answer_model)
        self.chunk_size = min(tokenizer_q.model_max_length, tokenizer_a.model_max_length, self.chunk_size)
        self.initialized = True
        logger.info("QA generator models loaded successfully.")

    def status(self) -> bool:
        return self.initialized
    
    def split_text(self, text: str) -> List[str]:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(self.question_model)
        tokens = tokenizer(text, return_tensors="pt", truncation=False)["input_ids"][0]
        chunks = []
        for i in range(0, len(tokens), self.chunk_size):
            chunk = tokenizer.decode(tokens[i:i + self.chunk_size], skip_special_tokens=True)
            chunks.append(chunk)
        return chunks

    async def generate_qa_pairs(self, text: str, doc_id: str) -> List[SQuADExample]:
        if not self.initialized:
            logger.info(f"Before model load: {psutil.Process().memory_info().rss / (1024*1024):.2f} MB")
            await self.init_models()
        
        logger.info(f"After model load: {psutil.Process().memory_info().rss / (1024*1024):.2f} MB")

        qa_dataset = []
        chunks = self.split_text(text)
        empty_answers = 0

        for i, chunk in enumerate(chunks):
            try:
                prompt = f"Generate {self.max_questions_per_chunk} questions from the following text:\n{chunk}"
                outputs = self.question_generator(prompt, num_return_sequences=1)

                # Try to split multi-line output into individual questions
                raw_output = outputs[0]['generated_text']
                questions = [q.strip() for q in raw_output.split('\n') if q.strip()]
                questions = questions[:self.max_questions_per_chunk]

                for j, question in enumerate(questions):
                    try:
                        answer = self.answer_extractor(question=question, context=chunk)
                        answer_text = answer.get("answer", "").strip()
                        if not answer_text:
                            empty_answers += 1
                            logger.warning(f"Empty answer for Q{i}-{j}: {question}")
                            continue

                        qa_dataset.append(SQuADExample(
                            context=chunk,
                            question=question,
                            answer=answer_text,
                            answer_start=answer.get("start", -1),
                            id=f"{doc_id}_chunk_{i}_qa_{j}"
                        ))

                    except Exception as e:
                        logger.warning(f"Failed to extract answer for Q{i}-{j}: {question} -> {e}")
                        continue

            except Exception as e:
                logger.warning(f"Failed to generate questions for chunk {i}: {e}")
                continue

        await asyncio.sleep(0)  # cooperative multitasking
        logger.info(f"Processed {len(chunks)} chunks, generated {len(qa_dataset)} QA pairs. empty answers: {empty_answers}")
        return qa_dataset


