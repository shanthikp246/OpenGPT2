# blobstore/base.py
from abc import ABC, abstractmethod

class BlobStore(ABC):
    @abstractmethod
    def list_files(self): pass

    @abstractmethod
    def read_file(self, file_path: str): pass

    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str): pass

    @abstractmethod
    def download_file(self, remote_path: str, local_path: str): pass

    @abstractmethod
    def write_file(self, file_path: str, content: str): pass

    @abstractmethod
    def exists(self, file_path: str): pass

    def make_dirs_if_needed(self, file_path: str):
        raise NotImplementedError


