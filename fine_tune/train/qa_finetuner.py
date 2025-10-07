import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from datasets import Dataset, load_metric
from transformers import (
    AutoModelForQuestionAnswering,
    AutoTokenizer,
    EvalPrediction,
    Trainer,
    TrainingArguments,
    pipeline,
)

from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

from ..blobstore.base import BlobStore

class QAFineTuner:
    def __init__(
            self,
            blobstore: BlobStore,
            model_name="distilbert-base-cased", 
            output_dir="./checkpoints",
    ):
        self.model_name = model_name
        self.output_dir = output_dir
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.blobstore = blobstore
        # Load base model
        self.base_model = AutoModelForQuestionAnswering.from_pretrained(model_name)
        self.model = prepare_model_for_kbit_training(self.base_model)

        # Define LoRA config
        lora_config = LoraConfig(
            r=8,
            lora_alpha=16,
            target_modules=["q_lin", "v_lin"],
            lora_dropout=0.05,
            bias="none",
        )

        self.model = get_peft_model(self.model, lora_config)

    def _resolve_blob_path(self, qa_data_path: str) -> str:
        if qa_data_path.startswith("s3://"):
            _, _, remainder = qa_data_path.partition("://")
            _, _, key = remainder.partition("/")
            return key
        return qa_data_path

    def _load_dataset(self, qa_data_path: str) -> List[Dict[str, Any]]:
        resolved_path = self._resolve_blob_path(qa_data_path)

        dataset_bytes: bytes | None = None
        if self.blobstore and self.blobstore.exists(resolved_path):
            dataset_bytes = self.blobstore.read_file(resolved_path)

        if dataset_bytes is None:
            local_path = Path(resolved_path).expanduser()
            if not local_path.exists():
                raise FileNotFoundError(f"QA dataset not found at {resolved_path}")
            dataset_bytes = local_path.read_bytes()

        qa_pairs_json = json.loads(dataset_bytes.decode("utf-8"))

        # Normalise both flattened and SQuAD-style datasets into a consistent list of examples
        if isinstance(qa_pairs_json, dict) and "data" in qa_pairs_json:
            examples: List[Dict[str, Any]] = []
            for article in qa_pairs_json.get("data", []):
                title = article.get("title")
                for paragraph in article.get("paragraphs", []):
                    context = paragraph.get("context", "")
                    for qa in paragraph.get("qas", []):
                        answers = qa.get("answers", [])
                        examples.append(
                            {
                                "id": qa.get("id"),
                                "title": title,
                                "context": context,
                                "question": qa.get("question"),
                                "answers": answers,
                            }
                        )
            return examples

        if not isinstance(qa_pairs_json, list):
            raise ValueError("QA dataset must be a list or a SQuAD-style mapping with 'data'.")

        return qa_pairs_json

    def prepare_data(self, qa_data_path):
        qa_pairs = self._load_dataset(qa_data_path)
        print(f"📊 Loading {len(qa_pairs)} QA pairs...")
        examples = []
        for item in qa_pairs:
            # print(item)
            # see generator_exttactor.py generate_qa_pairs() for format
            context = item.get("context", "")
            question = item.get("question", "")

            if not context or not question:
                continue
            answers = item.get("answers", [])
            if isinstance(answers, dict):
                # Backwards compatibility with the previous array-of-dicts format
                texts = answers.get("text", [])
                starts = answers.get("answer_start", [])
                answer = texts[0] if texts else ""
                answer_start = starts[0] if starts else -1
            else:
                answer_dict = answers[0] if answers else {}
                answer = answer_dict.get("text", "")
                answer_start = answer_dict.get("answer_start", -1)

            if answer_start == -1:
                continue  # skip if answer not found

            examples.append({
                "context": context,
                "question": question,
                "answers": {"text": [answer], "answer_start": [answer_start]}
            })

        if not examples:
            raise ValueError("No valid QA pairs found in the dataset.")

        dataset = Dataset.from_list(examples)
        dataset = dataset.train_test_split(test_size=0.1)
        train_dataset = dataset["train"]
        eval_dataset = dataset["test"]

        # Tokenize both
        tokenized_train = train_dataset.map(self.tokenize_examples, 
                                            batched=True, 
                                            remove_columns=train_dataset.column_names)
        tokenized_eval = eval_dataset.map(self.tokenize_examples, 
                                          batched=True, 
                                          remove_columns=eval_dataset.column_names)
        return tokenized_train, tokenized_eval

    def compute_metrics(self, p: EvalPrediction):
        pred_start, pred_end = np.argmax(p.predictions[0], axis=1), np.argmax(p.predictions[1], axis=1)
        exact_matches = [s == l["answer_start"][0] for s, l in zip(pred_start, p.label_ids)]
        return {"exact_match": np.mean(exact_matches)}
    
    def tokenize_examples(self, examples):
        """Tokenize QA examples for extractive fine-tuning."""
        # Hugging Face expects this structure for extractive QA (like SQuAD)
        tokenized = self.tokenizer(
            examples["question"],
            examples["context"],
            truncation="only_second",
            max_length=384,
            stride=128,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding="max_length"
        )

        #  Drop offset_mapping and other fields before returning
        tokenized.pop("offset_mapping", None)
        tokenized.pop("overflow_to_sample_mapping", None)
        return tokenized

    def train(self, qa_data_path):
        tokenized_train, tokenized_eval = self.prepare_data(qa_data_path)
        
        training_args = TrainingArguments(
            output_dir=self.output_dir,
            evaluation_strategy="epoch",
            per_device_train_batch_size=8,
            per_device_eval_batch_size=8,
            num_train_epochs=3,
            save_steps=500,
            save_total_limit=2,
            logging_steps=10,
            remove_unused_columns=False,
            push_to_hub=False,
            do_eval=True,
            eval_steps=50,
        )

        trainer = Trainer(
            model=self.model,
            train_dataset=tokenized_train,
            eval_dataset=tokenized_eval,
            tokenizer=self.tokenizer,
            args=training_args,
            compute_metrics=self.compute_metrics
        )

        trainer.train()
        self.save_model_to_blobstore(
            trainer,
            self.tokenizer,
        )
       
    def register_inference_model(self):
        model = AutoModelForQuestionAnswering.from_pretrained(self.output_dir)
        tokenizer = AutoTokenizer.from_pretrained(self.output_dir)
        return pipeline("question-answering", model=model, tokenizer=tokenizer)

    def run_pipeline(self, qa_data_path):
        self.train(qa_data_path)
        return self.register_inference_model()
    
    def evaluate(self, qa_data_path: str) -> dict:
        # Load the fine-tuned model and tokenizer
        model = AutoModelForQuestionAnswering.from_pretrained(self.output_dir)
        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        qa_pipeline = pipeline("question-answering", model=model, tokenizer=tokenizer)

        qa_entries = self._load_dataset(qa_data_path)

        # Initialize evaluation metrics
        metric = load_metric("squad")
        for item in qa_entries:
            question = item.get("question")
            context = item.get("context")
            if not question or not context:
                continue

            answers = item.get("answers", {})
            if isinstance(answers, dict):
                answer_texts = answers.get("text", [])
                formatted_answers = {
                    "text": answer_texts,
                    "answer_start": answers.get("answer_start", []),
                }
            else:
                answer_texts = [ans.get("text") for ans in answers if ans.get("text")]
                formatted_answers = {
                    "text": answer_texts,
                    "answer_start": [ans.get("answer_start", -1) for ans in answers],
                }

            if not answer_texts:
                continue

            prediction = qa_pipeline(question=question, context=context)
            predicted_answer = prediction["answer"]

            metric.add(
                prediction={
                    "id": str(item.get("id", "0")),
                    "prediction_text": predicted_answer,
                },
                reference={
                    "id": str(item.get("id", "0")),
                    "answers": formatted_answers,
                },
            )

        # Compute final metrics
        results = metric.compute()
        return {
            "exact_match": results["exact_match"],
            "f1": results["f1"],
        }

    def save_model_to_blobstore(
        self,
        trainer: Trainer,
        tokenizer: AutoTokenizer,
    ) -> None:
        """Persist the fine-tuned artefacts to the configured blobstore."""
        # Create a temporary local directory to hold the model
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Save model and tokenizer locally
            trainer.save_model(tmp_path)
            tokenizer.save_pretrained(tmp_path)

            # Upload all files in the temp dir to blobstore
            for file_path in tmp_path.glob("*"):
                remote_path = os.path.join(self.output_dir, file_path.name)
                self.blobstore.upload_file(str(file_path), remote_path)

            print(f"✅ Model and tokenizer uploaded to {self.output_dir} via blobstore.")


