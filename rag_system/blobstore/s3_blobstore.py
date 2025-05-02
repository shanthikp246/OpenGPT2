import boto3
from botocore.exceptions import ClientError
from .base import BlobStore

class S3BlobStore(BlobStore):
    def __init__(self, bucket: str, prefix: str = ""):
        self.bucket = bucket
        self.prefix = prefix.rstrip("/")
        self.s3 = boto3.client("s3")

    def _full_key(self, path: str) -> str:
        return f"{self.prefix}/{path}".lstrip("/")

    def list_files(self):
        response = self.s3.list_objects_v2(Bucket=self.bucket, Prefix=self.prefix)
        return [obj['Key'] for obj in response.get('Contents', [])]

    def read_file(self, path: str) -> str:
        key = self._full_key(path)
        obj = self.s3.get_object(Bucket=self.bucket, Key=key)
        return obj['Body'].read().decode("utf-8")

    def upload_file(self, local_path: str, remote_path: str):
        key = self._full_key(remote_path)
        self.s3.upload_file(local_path, self.bucket, key)

    def download_file(self, remote_path: str, local_path: str):
        key = self._full_key(remote_path)
        self.s3.download_file(self.bucket, key, local_path)

    def exists(self, remote_path: str) -> bool:
        key = self._full_key(remote_path)
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response['Error']['Code'] == "404":
                return False
            raise
