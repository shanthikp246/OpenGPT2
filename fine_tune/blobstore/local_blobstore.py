import os
from typing import List

from .base import BlobStore

class LocalBlobStore(BlobStore):
    def __init__(self, directory: str):
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)

    def list_files(self) -> List[str]:
        if not os.path.isdir(self.directory):
            return []

        supported_extensions = {".pdf", ".txt"}
        return [
            os.path.join(self.directory, f)
            for f in os.listdir(self.directory)
            if os.path.splitext(f)[1].lower() in supported_extensions
        ]

    def read_file(self, file_path: str) -> str:
        with open(file_path, "rb") as f:
            return f.read()

    def upload_file(self, local_path: str, dest_path: str) -> None:
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(local_path, "rb") as src, open(dest_path, "wb") as dest:
            dest.write(src.read())

    def download_file(self, source_path: str, local_path: str) -> None:
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(source_path, "rb") as src, open(local_path, "wb") as dest:
            dest.write(src.read())

    def exists(self, file_path: str) -> bool:
        return os.path.exists(file_path)
    
    def write_file(self, file_path: str, content: str):
        self.make_dirs_if_needed(file_path)
        with open(file_path, "w") as f:
            f.write(content)

    def make_dirs_if_needed(self, file_path: str):
        dir_path = os.path.dirname(file_path)
        os.makedirs(dir_path, exist_ok=True)

