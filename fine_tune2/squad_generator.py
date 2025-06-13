# squad_generator.py
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from interfaces import *
from implementations import *

logger = logging.getLogger(__name__)

class SQuADDatasetGenerator:
    def __init__(
        self,
        blob_store: IBlobStore,
        document_extractor: IDocumentExtractor,
        qa_generator: IQAGenerator,
        status_tracker: IStatusTracker
    ):
        self.blob_store = blob_store
        self.document_extractor = document_extractor
        self.qa_generator = qa_generator
        self.status_tracker = status_tracker

    async def init_models(self):
        await self.qa_generator.init_models()
    
    
    async def generate_dataset_task(self, task_id: str, bucket_name: str):
        """Background task to process all files in S3 bucket"""
        try:
            logger.info(f"Starting dataset generation for bucket: {bucket_name}")
            import psutil
            logger.info(f"Memory used at startup: {psutil.Process().memory_info().rss / 1024**2:.2f} MB")

            # Update status to running
            status = await self.status_tracker.get_status(task_id)
            status.status = "running"
            await self.status_tracker.update_status(task_id, status)
            
            # List all files in bucket
            files = await self.blob_store.list_files(bucket_name)
            supported_extensions = {'.pdf', '.txt'}
            
            # Filter supported files
            supported_files = [
                f for f in files 
                if Path(f.key).suffix.lower() in supported_extensions
            ]
            
            status.total_files = len(supported_files)
            await self.status_tracker.update_status(task_id, status)
            
            logger.info(f"Found {len(supported_files)} supported files to process")
            
            # Process files and generate QA pairs
            all_qa_pairs = []
            
            for file_info in supported_files:
                try:
                    qa_pairs = await self._process_file(bucket_name, file_info)
                    all_qa_pairs.extend(qa_pairs)
                    
                    # Update progress
                    status.processed_files += 1
                    status.generated_examples = len(all_qa_pairs)
                    await self.status_tracker.update_status(task_id, status)
                    
                    logger.info(f"Processed {file_info.key}: {len(qa_pairs)} QA pairs generated")
                    
                except Exception as e:
                    logger.error(f"Error processing file {file_info.key}: {e}")
                    continue
            
            # Convert to SQuAD format and save
            squad_dataset = self._convert_to_squad_format(all_qa_pairs, task_id)
            await self._save_dataset(bucket_name, squad_dataset, task_id)
            
            # Mark as completed
            status.status = "completed"
            status.completed_at = datetime.utcnow().isoformat()
            await self.status_tracker.update_status(task_id, status)
            
            logger.info(f"Dataset generation completed. Generated {len(all_qa_pairs)} QA pairs")
            
        except Exception as e:
            logger.exception(f"Uncaught error in background generation task for {task_id}: {e}")
            
            # Mark as failed
            status = await self.status_tracker.get_status(task_id)
            status.status = "failed"
            status.error_message = str(e)
            status.completed_at = datetime.utcnow().isoformat()
            await self.status_tracker.update_status(task_id, status)
    
    async def _process_file(self, bucket_name: str, file_info: FileInfo) -> List[SQuADExample]:
        """Process a single file and generate QA pairs"""
        try:
            # Read file content
            file_content = await self.blob_store.read_file(bucket_name, file_info.key)
            
            # Extract text
            file_extension = Path(file_info.key).suffix
            text = await self.document_extractor.extract_text(file_content, file_extension)
            
            if not text or len(text.strip()) < 100:
                logger.warning(f"Insufficient text extracted from {file_info.key}")
                return []
            
            # Generate QA pairs
            doc_id = Path(file_info.key).stem
            qa_pairs = await self.qa_generator.generate_qa_pairs(text, doc_id)
            
            return qa_pairs
            
        except Exception as e:
            logger.error(f"Error processing file {file_info.key}: {e}")
            return []
    
    def _convert_to_squad_format(self, qa_pairs: List[SQuADExample], task_id: str) -> Dict[str, Any]:
        """Convert QA pairs to SQuAD format"""
        squad_data = {
            "version": "2.0",
            "data": []
        }
        
        # Group by context
        context_groups = {}
        for qa in qa_pairs:
            if qa.context not in context_groups:
                context_groups[qa.context] = []
            context_groups[qa.context].append(qa)
        
        # Convert to SQuAD format
        for context, qa_list in context_groups.items():
            qas = []
            for qa in qa_list:
                qas.append({
                    "id": qa.id,
                    "question": qa.question,
                    "answers": [
                        {
                            "text": qa.answer,
                            "answer_start": qa.answer_start
                        }
                    ]
                })
            
            squad_data["data"].append({
                "title": f"Generated_Document_{task_id}",
                "paragraphs": [
                    {
                        "context": context,
                        "qas": qas
                    }
                ]
            })
        
        return squad_data
    
    async def _save_dataset(self, bucket_name: str, squad_dataset: Dict[str, Any], task_id: str):
        """Save generated dataset to S3"""
        try:
            # Save as JSON
            json_content = json.dumps(squad_dataset, indent=2, ensure_ascii=False)
            json_key = f"generated_datasets/squad_dataset_{task_id}.json"
            
            await self.blob_store.write_file(
                bucket_name, 
                json_key, 
                json_content.encode('utf-8')
            )
            
            logger.info(f"Dataset saved to s3://{bucket_name}/{json_key}")
            
        except Exception as e:
            logger.error(f"Error saving dataset: {e}")
            raise
    
    async def get_generation_status(self, task_id: str) -> Optional[GenerationStatus]:
        """Get status of generation task"""
        return await self.status_tracker.get_status(task_id)