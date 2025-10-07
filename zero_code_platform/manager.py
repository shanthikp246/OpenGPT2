"""Runtime orchestration for the zero-code platform."""

from __future__ import annotations

from dataclasses import dataclass

import uvicorn

from .config import PlatformConfig


@dataclass
class ServiceHandle:
    """Small helper that keeps track of service metadata."""

    name: str
    host: str
    port: int


class ZeroCodePlatform:
    """High-level orchestrator that wires configuration into running services."""

    def __init__(self, config: PlatformConfig):
        self.config = config

    # ------------------------------------------------------------------
    # RAG
    # ------------------------------------------------------------------
    def build_rag_app(self):
        if not self.config.rag:
            raise RuntimeError("RAG configuration not provided.")

        rag_config = self.config.rag

        if rag_config.mode == "local":
            from rag_system.orchestrator.local_orchestrator import LocalRAGOrchestrator

            orchestrator = LocalRAGOrchestrator(
                doc_path=rag_config.documents_path or "./documents",
                index_path=rag_config.index_path,
            )
        else:
            from rag_system.orchestrator.aws_orchestrator import AwsRAGOrchestrator

            orchestrator = AwsRAGOrchestrator(
                s3_bucket=rag_config.s3_bucket or "",
                s3_prefix=rag_config.s3_prefix,
                index_path=rag_config.index_path,
            )

        from rag_system.app.app_factory import create_app

        return create_app(orchestrator)

    def run_rag_service(self) -> ServiceHandle:
        rag_config = self.config.rag
        if not rag_config:
            raise RuntimeError("RAG configuration not provided.")

        app = self.build_rag_app()
        uvicorn.run(app, host=rag_config.host, port=rag_config.port, log_level="info")
        return ServiceHandle("rag", rag_config.host, rag_config.port)

    # ------------------------------------------------------------------
    # Fine-tuning
    # ------------------------------------------------------------------
    def build_finetune_app(self):
        if not self.config.fine_tune:
            raise RuntimeError("Fine-tune configuration not provided.")

        ft_config = self.config.fine_tune

        from fine_tune.app.qa_app_factory import create_app as create_finetune_app
        from fine_tune.inference.local_inference import LocalInference

        inference = LocalInference(
            documents_path=ft_config.documents_path,
            qa_data_path=ft_config.qa_data_path,
            model_output_dir=ft_config.model_output_dir,
        )

        return create_finetune_app(inference, auto_initialize=ft_config.generate_on_startup)

    def run_finetune_service(self) -> ServiceHandle:
        ft_config = self.config.fine_tune
        if not ft_config:
            raise RuntimeError("Fine-tune configuration not provided.")

        app = self.build_finetune_app()
        uvicorn.run(app, host=ft_config.host, port=ft_config.port, log_level="info")
        return ServiceHandle("fine_tune", ft_config.host, ft_config.port)


__all__ = ["ZeroCodePlatform", "ServiceHandle"]
