from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
import torch
from .base import LLMModel

class FlanT5(LLMModel):
    def __init__(self, model_name="google/flan-t5-large"):
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model.to(self.device)

    def gen_prompt_few_shot(self, context, query):
        FEW_SHOT_EXAMPLES = """
You are a financial data extractor. Extract only the value asked for in the question using the provided context.
Do not guess. If the answer is not present in the context, say 'Not available'.

Context:
Tesla Inc. designs, develops, manufactures, leases, and sells electric vehicles and energy generation and storage systems.
Question: What does Tesla Inc. do?
Answer: Tesla designs and sells electric vehicles and energy systems.

Context:
The company's revenue increased 25% year-over-year due to increased Model Y sales.
Question: Why did Tesla's revenue increase?
Answer: Tesla's revenue increased due to higher sales of the Model Y.

Context:
{context}
Question: {query}
Answer:
"""
        prompt = FEW_SHOT_EXAMPLES.format(context=context, query=query)
        return prompt
    
    def gen_prompt_zero_shot(self, context, query):
        prompt = f"Context:\n{context}\n\nQuestion: {query}\nAnswer:"
        return prompt

    def generate(self, context, query):
        prompt = self.gen_prompt_few_shot(context, query)
        inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=512).to(self.device)
        outputs = self.model.generate(**inputs, max_new_tokens=250)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)
