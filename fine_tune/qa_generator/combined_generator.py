# qa_generator/combined_generator.py
from transformers import pipeline

class CombinedQAGenerator(QAGenerator):
    def __init__(self):
        self.generator = pipeline("text2text-generation", model="google/flan-t5-large")
        self.extractor = pipeline("question-answering", model="distilbert-base-cased-distilled-squad")

    def generate(self, text: str):
        prompts = [
            f"Generate 3 questions and answers from the following context:\n{text[:1000]}"
        ]
        results = []
        for prompt in prompts:
            output = self.generator(prompt, max_length=256)[0]['generated_text']
            # optionally postprocess output into question-answer pairs
            # You could also use extractive QA with keyword filtering
            results.append({"question": "...", "answer": "...", "context": text[:1000]})
        return results

