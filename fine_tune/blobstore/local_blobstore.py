import os
from blobstore.base import BlobStore
from typing import List

class LocalBlobStore(BlobStore):
    def __init__(self, directory: str):
        self.directory = directory

    def list_files(self) -> List[str]:
        return [
            os.path.join(self.directory, f)
            for f in os.listdir(self.directory)
            if f.lower().endswith(".pdf")
        ]

    def read_file(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return f.read()

    def upload_file(self, local_path: str, dest_path: str) -> None:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(local_path, "rb") as src, open(dest_path, "wb") as dest:
            dest.write(src.read())

    def download_file(self, source_path: str, local_path: str) -> None:
        self.upload_file(source_path, local_path)

    def exists(self, file_path: str) -> bool:
        return os.path.exists(file_path)

    def write_file(self, file_path: str, content: str) -> None:
        with open(file_path, "w") as f:
            f.write(content)

