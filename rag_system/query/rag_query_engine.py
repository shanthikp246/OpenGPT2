from embedding.base import EmbeddingModel
from vectordb.base import VectorDB
from llm.base import LLMModel

class RAGQueryEngine:
    def __init__(self, embedder: EmbeddingModel, vectordb: VectorDB, llm: LLMModel):
        self.embedder = embedder
        self.vectordb = vectordb
        self.llm = llm

    def query(self, query_text: str, top_k=3):
        q_embedding = self.embedder.embed([query_text])[0]
        context_chunks = self.vectordb.query(q_embedding, top_k)
        context = "\n".join(context_chunks)
        respone = self.llm.generate(context, query_text)
        return {"context": context, "response": respone}
