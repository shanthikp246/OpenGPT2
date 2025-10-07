from .app_factory import create_app
from ..orchestrator.local_orchestrator import LocalRAGOrchestrator

orchestrator = LocalRAGOrchestrator(
    doc_path="./documents",
    index_path="vector_index/index.bin",
)

app = create_app(orchestrator)
