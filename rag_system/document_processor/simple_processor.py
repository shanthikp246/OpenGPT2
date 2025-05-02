import textwrap
from ..blobstore.base import BlobStore
from .base import DocumentProcessor

class SimpleProcessor(DocumentProcessor):
    def __init__(self, blobstore: BlobStore, chunk_size=500):
        self.blobstore = blobstore
        self.chunk_size = chunk_size

    def process(self):
        chunks = []
        for file_path in self.blobstore.list_files():
            text = self.blobstore.read_file(file_path)
            chunks.extend(textwrap.wrap(text, self.chunk_size))
        return chunks
