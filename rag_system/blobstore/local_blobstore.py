import os
from .base import BlobStore

class LocalBlobStore(BlobStore):
    def __init__(self, base_path: str):
        self.base_path = os.path.abspath(base_path)

    def _full_path(self, path: str) -> str:
        return os.path.join(self.base_path, path)

    def list_files(self):
        file_list = []
        for root, _, files in os.walk(self.base_path):
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, self.base_path)
                file_list.append(rel)
        return file_list

    def read_file(self, path: str) -> str:
        full_path = self._full_path(path)
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    def upload_file(self, local_path: str, remote_path: str):
        dest = self._full_path(remote_path)
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(local_path, "rb") as src, open(dest, "wb") as dst:
            dst.write(src.read())

    def download_file(self, remote_path: str, local_path: str):
        src = self._full_path(remote_path)
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(src, "rb") as f_src, open(local_path, "wb") as f_dst:
            f_dst.write(f_src.read())

    def exists(self, remote_path: str) -> bool:
        return os.path.exists(self._full_path(remote_path))
