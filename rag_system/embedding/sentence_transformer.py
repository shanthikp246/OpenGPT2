from sentence_transformers import SentenceTransformer
from .base import EmbeddingModel

class SentenceTransformerEmbedding(EmbeddingModel):
    def __init__(self, model_name='sentence-transformers/all-MiniLM-L6-v2'):
        self.model = SentenceTransformer(model_name)

    def embed(self, texts):
        return self.model.encode(texts, show_progress_bar=False)
