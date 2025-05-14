import boto3
import os
import json
import tempfile
from typing import List
from botocore.exceptions import ClientError

class S3BlobStore:
    def __init__(self, bucket: str, prefix: str = ""):
        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self.s3 = boto3.client("s3")

    def _s3_key(self, path: str) -> str:
        return f"{self.prefix}/{path}".strip("/") if self.prefix else path

    def list_files(self) -> List[str]:
        paginator = self.s3.get_paginator("list_objects_v2")
        operation_parameters = {"Bucket": self.bucket, "Prefix": self.prefix}
        page_iterator = paginator.paginate(**operation_parameters)

        files = []
        for page in page_iterator:
            for content in page.get("Contents", []):
                key = content["Key"]
                if not key.endswith("/"):
                    files.append(key)
        return files

    def read_file(self, path: str) -> str:
        key = self._s3_key(path)
        obj = self.s3.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read().decode("utf-8")

    def write_file(self, path: str, data: str):
        key = self._s3_key(path)
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data.encode("utf-8"))

    def exists(self, path: str) -> bool:
        key = self._s3_key(path)
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return False
            raise

    def upload_directory(self, local_dir: str):
        for root, _, files in os.walk(local_dir):
            for file in files:
                local_path = os.path.join(root, file)
                rel_path = os.path.relpath(local_path, local_dir)
                s3_key = self._s3_key(rel_path)
                self.s3.upload_file(local_path, self.bucket, s3_key)

    def download_directory(self, local_dir: str):
        files = self.list_files()
        for key in files:
            rel_path = key[len(self.prefix)+1:] if self.prefix else key
            local_path = os.path.join(local_dir, rel_path)
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            self.s3.download_file(self.bucket, key, local_path)


