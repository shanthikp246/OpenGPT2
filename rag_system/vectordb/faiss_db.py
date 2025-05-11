import faiss
import pickle
import os
import tempfile
import numpy as np
from .base import VectorDB

class FAISSVectorDB(VectorDB):
    def __init__(self, blobstore, index_path="vector_index/index.bin"):
        self.blobstore = blobstore
        self.index_path = index_path
        self.index = None
        self.docs = []

    def build_index(self, embeddings, documents):
        # called from orchestrator to build index
        dim = len(embeddings[0])
        self.index = faiss.IndexFlatL2(dim)
        self.index.add(np.array(embeddings).astype('float32'))
        self.docs = documents
        self._save()

    def query(self, embedding, k):
        D, I = self.index.search(np.array([embedding]).astype('float32'), k)
        return [self.docs[i]["text"] for i in I[0]]

    def _save(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            index_fp = os.path.join(tmpdir, "index.bin")
            meta_fp = os.path.join(tmpdir, "docs.pkl")
            faiss.write_index(self.index, index_fp)
            with open(meta_fp, "wb") as f:
                pickle.dump(self.docs, f)
            self.blobstore.upload_file(index_fp, self.index_path)
            self.blobstore.upload_file(meta_fp, self.index_path.replace(".bin", ".pkl"))

    def load(self):
        if not self.blobstore.exists(self.index_path):
            return False
        with tempfile.TemporaryDirectory() as tmpdir:
            index_fp = os.path.join(tmpdir, "index.bin")
            meta_fp = os.path.join(tmpdir, "docs.pkl")
            self.blobstore.download_file(self.index_path, index_fp)
            self.blobstore.download_file(self.index_path.replace(".bin", ".pkl"), meta_fp)
            self.index = faiss.read_index(index_fp)
            with open(meta_fp, "rb") as f:
                self.docs = pickle.load(f)
        return True
