import os
import json
from datasets import Dataset
from transformers import AutoTokenizer, AutoModelForQuestionAnswering, TrainingArguments, Trainer, EvalPrediction
from peft import LoraConfig, get_peft_model, TaskType, prepare_model_for_kbit_training
from trl import SFTTrainer
import numpy as np

class QAFineTuner:
    def __init__(self, model_name="distilbert-base-cased", output_dir="./checkpoints"):
        self.model_name = model_name
        self.output_dir = output_dir
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

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
            task_type=TaskType.QUESTION_ANSWERING,
        )

        self.model = get_peft_model(self.model, lora_config)

    def prepare_data(self, qa_data_path):
        with open(qa_data_path, "r") as f:
            qa_pairs = json.load(f)

        examples = []
        for item in qa_pairs:
            context = item["context"]
            question = item["question"]
            answer = item["answer"]
            answer_start = context.find(answer)

            if answer_start == -1:
                continue  # skip if answer not found

            examples.append({
                "context": context,
                "question": question,
                "answers": {"text": [answer], "answer_start": [answer_start]}
            })

        dataset = Dataset.from_list(examples)
        return dataset

    def compute_metrics(self, p: EvalPrediction):
        pred_start, pred_end = np.argmax(p.predictions[0], axis=1), np.argmax(p.predictions[1], axis=1)
        exact_matches = [s == l["answer_start"][0] for s, l in zip(pred_start, p.label_ids)]
        return {"exact_match": np.mean(exact_matches)}

    def train(self, qa_data_path):
        dataset = self.prepare_data(qa_data_path)

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
            train_dataset=dataset,
            eval_dataset=dataset,
            tokenizer=self.tokenizer,
            args=training_args,
            compute_metrics=self.compute_metrics
        )

        trainer.train()
        trainer.save_model(self.output_dir)
        self.tokenizer.save_pretrained(self.output_dir)

    def register_inference_model(self):
        from transformers import pipeline, AutoModelForQuestionAnswering
        model = AutoModelForQuestionAnswering.from_pretrained(self.output_dir)
        tokenizer = AutoTokenizer.from_pretrained(self.output_dir)
        return pipeline("question-answering", model=model, tokenizer=tokenizer)

    def run_pipeline(self, qa_data_path):
        self.train(qa_data_path)
        return self.register_inference_model()

