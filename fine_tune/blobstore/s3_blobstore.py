import os
from typing import List

import boto3
from botocore.exceptions import ClientError

from .base import BlobStore


class S3BlobStore(BlobStore):
    def __init__(self, bucket_name: str, prefix: str = ""):
        self.s3 = boto3.client("s3")
        self.bucket = bucket_name
        self.prefix = prefix.strip("/")  # optional prefix within the bucket

    def _full_key(self, key: str) -> str:
        return f"{self.prefix}/{key}".lstrip("/") if self.prefix else key

    def list_files(self) -> List[str]:
        paginator = self.s3.get_paginator("list_objects_v2")
        result: List[str] = []
        prefix = self.prefix or ""
        for page in paginator.paginate(Bucket=self.bucket, Prefix=prefix):
            result.extend(obj["Key"] for obj in page.get("Contents", []))
        return result

    def read_file(self, file_path: str) -> bytes:
        key = self._full_key(file_path)
        obj = self.s3.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()

    def upload_file(self, local_path: str, remote_path: str) -> None:
        key = self._full_key(remote_path)
        self.s3.upload_file(local_path, self.bucket, key)

    def download_file(self, remote_path: str, local_path: str) -> None:
        key = self._full_key(remote_path)
        directory = os.path.dirname(local_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.s3.download_file(self.bucket, key, local_path)

    def write_file(self, file_path: str, content: str | bytes) -> None:
        key = self._full_key(file_path)
        if isinstance(content, str):
            content = content.encode("utf-8")
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=content)

    def make_dirs_if_needed(self, file_path: str) -> None:  # pragma: no cover - noop
        return None

    def exists(self, file_path: str) -> bool:
        key = self._full_key(file_path)
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            error_code = exc.response.get("Error", {}).get("Code")
            if error_code in {"404", "NoSuchKey"}:
                return False
            raise
