"""FastAPI application for orchestrating AWS-based SQuAD generation and fine-tuning."""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from ..blobstore.s3_blobstore import S3BlobStore
from ..parser.pdf_parser import PDFParser
from ..qa_generator.generator_extractor import GeneratorExtractorQAGenerator
from ..train.qa_finetuner import QAFineTuner


class SquadRequest(BaseModel):
    bucket: str = Field(..., description="S3 bucket that stores the source documents")
    documents_prefix: str = Field(
        "",
        description="Optional prefix to scope which documents are used for dataset generation.",
    )
    dataset_key: str = Field(
        "datasets/qa_pairs.json",
        description="Key inside the bucket where the generated SQuAD dataset will be saved.",
    )
    chunk_size: int = Field(500, ge=50, description="Approximate characters per chunk used for question generation.")
    max_questions_per_chunk: int = Field(
        3,
        ge=1,
        le=10,
        description="Upper bound for the number of questions asked per document chunk.",
    )


class FineTuneRequest(BaseModel):
    bucket: str = Field(..., description="S3 bucket that stores both dataset and model artifacts.")
    dataset_key: str = Field(..., description="Key of the SQuAD formatted dataset to fine-tune on.")
    model_output_prefix: str = Field(
        "checkpoints/finetuned-model",
        description="Prefix for where the fine-tuned model artifacts will be written.",
    )
    model_name: str = Field(
        "distilbert-base-cased",
        description="Hugging Face model identifier used as the base for LoRA fine-tuning.",
    )


app = FastAPI(title="AWS Fine-tuning Service")


@app.post("/squad")
async def create_squad_dataset(request: SquadRequest):
    blobstore = S3BlobStore(request.bucket)
    parser = PDFParser()

    try:
        generator = GeneratorExtractorQAGenerator(
            blobstore=blobstore,
            parser=parser,
            output_path=request.dataset_key,
            chunk_size=request.chunk_size,
            max_questions_per_chunk=request.max_questions_per_chunk,
            source_prefix=request.documents_prefix,
        )
        squad_dataset = generator.generate_qa_pairs()
    except Exception as exc:  # pragma: no cover - surfaced to client
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "dataset_key": f"s3://{request.bucket}/{request.dataset_key}",
        "examples": squad_dataset.get("metadata", {}).get(
            "total_examples",
            sum(
                len(paragraph.get("qas", []))
                for article in squad_dataset.get("data", [])
                for paragraph in article.get("paragraphs", [])
            ),
        ),
        "metadata": squad_dataset.get("metadata", {}),
    }


@app.post("/fine-tune")
async def fine_tune_model(request: FineTuneRequest):
    blobstore = S3BlobStore(request.bucket)

    try:
        finetuner = QAFineTuner(
            blobstore=blobstore,
            model_name=request.model_name,
            output_dir=request.model_output_prefix,
        )
        finetuner.train(request.dataset_key)
        metrics = finetuner.evaluate(request.dataset_key)
    except Exception as exc:  # pragma: no cover - surfaced to client
        raise HTTPException(status_code=500, detail=str(exc))

    return {
        "model_artifacts_prefix": f"s3://{request.bucket}/{request.model_output_prefix}",
        "metrics": metrics,
    }


@app.get("/")
async def root():
    return {"message": "AWS fine-tuning orchestration is online."}
