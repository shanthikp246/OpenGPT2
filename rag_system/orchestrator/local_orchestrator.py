from .orchestrator import RAGOrchestrator
from blobstore.local_blobstore import LocalBlobStore
from document_processor.simple_processor import SimpleDocumentProcessor
from embedding.sentence_transformer import SentenceTransformerEmbedding
from vectordb.faiss_db import FAISSVectorDB
from llm.flan_t5 import FlanT5
from query.rag_query_engine import RAGQueryEngine

class LocalRAGOrchestrator(RAGOrchestrator):
    def __init__(self, doc_path: str = './documents', index_path: str = "vector_index/index.faiss"):
        self.blobstore = LocalBlobStore(doc_path)
        self.processor = SimpleDocumentProcessor(self.blobstore)
        self.embedder = SentenceTransformerEmbedding()
        self.llm = FlanT5()
        self.vectordb = FAISSVectorDB(blobstore=self.blobstore, index_path=index_path)
        self.query_engine = None

    def initialize(self):
        if not self.vectordb.load():
            documents = self.processor.process()
            embeddings = self.embedder.embed(documents)
            self.vectordb.build_index(embeddings, documents)
        self.query_engine = RAGQueryEngine(self.embedder, self.vectordb, self.llm)

    def query(self, query: str, top_k: int = 3) -> str:
        if not self.query_engine:
            raise RuntimeError("RAG system not initialized.")
        return self.query_engine.query(query, top_k)
