"""Configuration helpers for the zero-code AI platform."""

from __future__ import annotations

from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, Field, ValidationError, root_validator


class RAGConfig(BaseModel):
    """Configuration for provisioning a Retrieval-Augmented Generation service."""

    mode: Literal["local", "aws"] = "local"
    documents_path: Optional[str] = Field(
        default=None,
        description="Local directory containing source documents (required for local mode).",
    )
    index_path: str = Field(
        default="vector_index/index.bin",
        description="Path (local or remote) where the FAISS index should be stored.",
    )
    s3_bucket: Optional[str] = Field(
        default=None,
        description="Name of the S3 bucket to use when mode='aws'.",
    )
    s3_prefix: str = Field(
        default="",
        description="Prefix inside the S3 bucket that contains RAG artefacts.",
    )
    host: str = "0.0.0.0"
    port: int = 8001

    @root_validator
    def validate_fields(cls, values):  # type: ignore[override]
        mode = values.get("mode")
        documents_path = values.get("documents_path")
        s3_bucket = values.get("s3_bucket")

        if mode == "local" and not documents_path:
            raise ValueError("'documents_path' is required when RAG mode is 'local'.")
        if mode == "aws" and not s3_bucket:
            raise ValueError("'s3_bucket' is required when RAG mode is 'aws'.")
        return values


class FineTuneConfig(BaseModel):
    """Configuration for provisioning the fine-tuning service."""

    documents_path: str = Field(
        default="./documents",
        description="Directory containing the source PDFs used to generate QA pairs.",
    )
    qa_data_path: str = Field(
        default="./checkpoints/qa_pairs.json",
        description="Destination path for the generated QA dataset in SQuAD format.",
    )
    model_output_dir: str = Field(
        default="./checkpoints",
        description="Directory or remote prefix where the fine-tuned model should be stored.",
    )
    host: str = "0.0.0.0"
    port: int = 8002
    generate_on_startup: bool = Field(
        default=True,
        description="Whether the pipeline should run automatically when the API starts.",
    )


class PlatformConfig(BaseModel):
    """Top level configuration that wires RAG and fine-tuning modules together."""

    rag: Optional[RAGConfig] = None
    fine_tune: Optional[FineTuneConfig] = Field(default=None, alias="fineTune")

    class Config:
        allow_population_by_field_name = True

    @classmethod
    def load(cls, path: str | Path) -> "PlatformConfig":
        """Load configuration from a YAML file."""
        with open(path, "r", encoding="utf-8") as handle:
            payload = yaml.safe_load(handle) or {}
        try:
            return cls.parse_obj(payload)
        except ValidationError as exc:  # pragma: no cover - validation errors are user facing
            raise ValueError(str(exc)) from exc

    @classmethod
    def example(cls) -> "PlatformConfig":
        """Return an example configuration that can be used as a template."""
        return cls(
            rag=RAGConfig(documents_path="./documents"),
            fine_tune=FineTuneConfig(),
        )

    @classmethod
    def write_example(cls, path: str | Path) -> Path:
        """Persist an example configuration to disk."""
        destination = Path(path)
        if destination.exists():
            raise FileExistsError(f"Config file '{destination}' already exists.")
        destination.write_text(cls.example().to_yaml(), encoding="utf-8")
        return destination

    def to_yaml(self) -> str:
        """Serialise the configuration as a YAML string."""
        payload = self.dict(by_alias=True, exclude_none=True)
        return yaml.safe_dump(payload, sort_keys=False)


__all__ = ["PlatformConfig", "RAGConfig", "FineTuneConfig"]
