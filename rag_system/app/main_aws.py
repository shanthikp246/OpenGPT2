from .app_factory import create_app
from ..orchestrator.aws_orchestrator import AwsRAGOrchestrator

orchestrator = AwsRAGOrchestrator(
    s3_bucket="your-s3-bucket",
    s3_prefix="your-data-prefix",
    index_path="vector_index/index.bin",
)

app = create_app(orchestrator)
