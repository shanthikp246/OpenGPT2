from abc import ABC, abstractmethod

class BlobStore(ABC):
    @abstractmethod
    def list_files(self) -> list[str]:
        pass

    @abstractmethod
    def read_file(self, path: str) -> str:
        pass

    @abstractmethod
    def upload_file(self, local_path: str, remote_path: str):
        """Upload a local file to the blobstore path"""
        pass

    @abstractmethod
    def download_file(self, remote_path: str, local_path: str):
        """Download a blobstore file to a local file path"""
        pass

    @abstractmethod
    def exists(self, remote_path: str) -> bool:
        """Check if a file exists in the blobstore"""
        pass
