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
from transformers import pipeline, AutoTokenizer, AutoModelForQuestionAnswering
import logging

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

class TransformerQuestionGenerator(IQuestionGenerator):
    def __init__(self):
        self.qa_pipeline = None
        self.tokenizer = None
        self._initialize_model()
    
    def _initialize_model(self):
        try:
            # Use a question generation model
            model_name = "distilbert-base-uncased-distilled-squad"
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.qa_pipeline = pipeline(
                "question-answering",
                model=model_name,
                tokenizer=self.tokenizer
            )
        except Exception as e:
            logger.error(f"Error initializing QA model: {e}")
            self.qa_pipeline = None
    
    async def generate_qa_pairs(self, context: str, doc_id: str) -> List[SQuADExample]:
        if not self.qa_pipeline:
            logger.error("QA pipeline not initialized")
            return []
        
        try:
            # Split context into chunks
            chunks = self._split_text(context, max_length=512)
            qa_pairs = []
            
            for i, chunk in enumerate(chunks):
                # Generate questions for this chunk
                questions = self._generate_questions_for_chunk(chunk)
                
                for j, question in enumerate(questions):
                    # Generate answer using the QA model
                    try:
                        result = self.qa_pipeline(question=question, context=chunk)
                        
                        qa_pairs.append(SQuADExample(
                            context=chunk,
                            question=question,
                            answer=result['answer'],
                            answer_start=result['start'],
                            id=f"{doc_id}_chunk_{i}_qa_{j}"
                        ))
                    except Exception as e:
                        logger.error(f"Error generating answer for question: {e}")
                        continue
            
            return qa_pairs
        except Exception as e:
            logger.error(f"Error generating QA pairs: {e}")
            return []
    
    def _split_text(self, text: str, max_length: int = 512) -> List[str]:
        # Simple sentence-based splitting
        sentences = re.split(r'[.!?]+', text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(current_chunk) + len(sentence) < max_length:
                current_chunk += sentence + ". "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + ". "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return [chunk for chunk in chunks if len(chunk) > 50]  # Filter out very short chunks
    
    def _generate_questions_for_chunk(self, chunk: str) -> List[str]:
        # Simple rule-based question generation
        # In a real implementation, you'd use a more sophisticated question generation model
        questions = []
        
        # Extract named entities and create questions
        words = chunk.split()
        
        # Who questions
        if any(word.lower() in ['he', 'she', 'they', 'person', 'people'] for word in words):
            questions.append("Who is mentioned in this text?")
        
        # What questions
        if any(word.lower() in ['what', 'which', 'how'] for word in words):
            questions.append("What is the main topic discussed?")
        
        # When questions
        if any(word.isdigit() or word.lower() in ['today', 'yesterday', 'year', 'month'] for word in words):
            questions.append("When did this occur?")
        
        # Where questions
        if any(word.lower() in ['where', 'location', 'place', 'city', 'country'] for word in words):
            questions.append("Where did this take place?")
        
        # Default questions
        if not questions:
            questions = [
                "What is the main point of this text?",
                "What information is provided in this passage?"
            ]
        
        return questions[:3]  # Limit to 3 questions per chunk

class InMemoryStatusTracker(IStatusTracker):
    def __init__(self):
        self.statuses: Dict[str, GenerationStatus] = {}
    
    async def update_status(self, task_id: str, status: GenerationStatus) -> None:
        self.statuses[task_id] = status
    
    async def get_status(self, task_id: str) -> Optional[GenerationStatus]:
        return self.statuses.get(task_id)