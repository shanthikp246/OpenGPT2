import os
import json
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForQuestionAnswering, TrainingArguments, Trainer, EvalPrediction
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from trl import SFTTrainer
import numpy as np
from transformers import AutoTokenizer, pipeline
from datasets import load_metric
from datasets import DatasetDict
import os
import tempfile
from pathlib import Path
from blobstore.base import BlobStore

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

    def prepare_data(self, qa_data_path):
        with open(qa_data_path, "r") as f:
            qa_pairs_json = json.load(f)

        qa_pairs = qa_pairs_json["data"]
        print(f"📊 Loading {len(qa_pairs)} QA pairs...")
        examples = []
        for item in qa_pairs:
            # print(item)
            # see generator_exttactor.py generate_qa_pairs() for format
            context = item["context"]
            question = item["question"]
            answer = item["answers"]["text"][0]
            answer_start = item["answers"]["answer_start"][0]

            if answer_start == -1:
                continue  # skip if answer not found

            examples.append({
                "context": context,
                "question": question,
                "answers": {"text": [answer], "answer_start": [answer_start]}
            })

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
        return (tokenized_train, tokenized_eval)

    def compute_metrics(self, p: EvalPrediction):
        pred_start, pred_end = np.argmax(p.predictions[0], axis=1), np.argmax(p.predictions[1], axis=1)
        exact_matches = [s == l["answer_start"][0] for s, l in zip(pred_start, p.label_ids)]
        return {"exact_match": np.mean(exact_matches)}
    
    def tokenize_examples(self, examples):
        # Hugging Face expects this structure for extractive QA (like SQuAD)
        tokenized =  self.tokenizer(
            examples["question"],
            examples["context"],
            truncation="only_second",
            max_length=384,
            stride=128,
            return_overflowing_tokens=True,
            return_offsets_mapping=True,
            padding="max_length"
        )

        # 🚫 Drop offset_mapping before returning
        del tokenized.pop("offset_mapping", None)
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
            self.blobstore, 
            self.output_dir)
       
    def register_inference_model(self):
        from transformers import pipeline, AutoModelForQuestionAnswering
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

        # Load the evaluation dataset
        with open(qa_data_path, "r") as f:
            qa_data = json.load(f)

        # Initialize evaluation metrics
        metric = load_metric("squad")
        for item in qa_data:
            question = item["question"]
            context = item["context"]
            true_answer = item["answer"]

            prediction = qa_pipeline(question=question, context=context)
            predicted_answer = prediction["answer"]

            # Add to metric computation
            metric.add(
                prediction={"id": str(item.get("id", "0")), "prediction_text": predicted_answer},
                reference={"id": str(item.get("id", "0")), "answers": {"text": [true_answer], "answer_start": [context.find(true_answer)]}},
            )

        # Compute final metrics
        results = metric.compute()
        return {
            "exact_match": results["exact_match"],
            "f1": results["f1"]
        }
    
    def save_model_to_blobstore(
            self, 
            trainer, 
            tokenizer,  
            output_path_prefix: str):
        # Create a temporary local directory to hold the model
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)

            # Save model and tokenizer locally
            trainer.save_model(tmp_path)
            tokenizer.save_pretrained(tmp_path)

            # Upload all files in the temp dir to blobstore
            for file_path in tmp_path.glob("*"):
                remote_path = os.path.join(output_path_prefix, file_path.name)
                self.blobstore.upload_file(str(file_path), remote_path)

            print(f"✅ Model and tokenizer uploaded to {output_path_prefix} via blobstore.")


