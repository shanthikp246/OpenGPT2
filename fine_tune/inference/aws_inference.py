from ..blobstore.s3_blobstore import S3BlobStore
from .base import BaseInference


class AwsInference(BaseInference):
    def __init__(self, s3_bucket: str, qa_data_key: str, model_output_prefix: str):
        super().__init__(qa_data_key, model_output_prefix)
        self.blobstore = S3BlobStore(s3_bucket, prefix="")

    def get_blobstore(self):
        return self.blobstore
