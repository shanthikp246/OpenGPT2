from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from .base import LLMModel

class FlanT5(LLMModel):
    def __init__(self, model_name="google/flan-t5-base"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)

    def generate(self, context, query):
        prompt = f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512).to(self.device)
        outputs = self.model.generate(**inputs, max_new_tokens=150)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
