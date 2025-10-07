# OpenGPT2

Zero-code platform for building Retrieval-Augmented Generation (RAG) and fine-tuned
question answering services.

## Prerequisites

- [AWS Copilot](https://aws.github.io/copilot-cli/) installed (`brew install aws/tap/copilot-cli`)
- [`jq`](https://stedolan.github.io/jq/) installed (`brew install jq`)
- AWS credentials configured for `us-west-2` (`aws configure`)
- Docker running if you plan to use the provided Dockerfiles

## Repository layout

- `rag_system/` – zero-code RAG application (FastAPI + FAISS + Flan-T5)
- `fine_tune/` – zero-code fine-tuning and inference pipeline
- `zero_code_platform/` – orchestration layer and CLI for running everything without writing code
- `platform.config.example.yaml` – ready-to-copy configuration template for local deployments

## Zero-code platform CLI

The `zero_code_platform` package exposes a CLI that allows you to configure and run RAG
and fine-tuning services from YAML without touching the codebase.

```bash
# 1. Create a config file (optional – you can also copy platform.config.example.yaml)
python -m zero_code_platform.cli init-config --path platform.config.yaml

# 2. Review/validate the config
python -m zero_code_platform.cli --config platform.config.yaml validate

# 3a. Run the RAG API (loads documents and spins up FastAPI)
python -m zero_code_platform.cli --config platform.config.yaml run rag

# 3b. Run the fine-tuning service (generates QA pairs, fine-tunes, serves inference)
python -m zero_code_platform.cli --config platform.config.yaml run fine_tune
```

Each service runs in its own process. Start them in separate terminals if you want RAG
and fine-tuned inference to be available simultaneously.

## RAG system overview

- Reads files from local disk or S3 and indexes content using FAISS.
- Generates embeddings with `sentence-transformers/all-MiniLM-L6-v2`.
- Uses `google/flan-t5-large` to generate answers given retrieved context.
- Exposes a FastAPI `/query` endpoint returning both the answer and the supporting context.

## Fine-tuning pipeline overview

- Parses source documents, generates SQuAD-style QA pairs automatically, and fine-tunes
  `distilbert-base-cased` with LoRA adapters.
- Stores model artefacts via the configured blobstore (local filesystem or S3 via extensions).
- Serves inference and exposes `/query` and `/status` endpoints once the pipeline completes.

### AWS fine-tuning API

Deploy `fine_tune/app/qa_aws.py` to expose two orchestration endpoints backed by S3:

- `POST /squad` – reads PDF/TXT documents from the specified bucket/prefix and writes a
  fully compliant SQuAD v1.1 dataset (default: `datasets/qa_pairs.json`). The response
  surfaces dataset metadata so you can quickly confirm how many examples were generated.
- `POST /fine-tune` – consumes the generated dataset, fine-tunes the base model on AWS, and
  uploads the resulting checkpoints (default: `checkpoints/finetuned-model`).

Both endpoints accept JSON payloads specifying the bucket, prefixes, and optional overrides for
chunk sizing or model identifiers so the entire workflow can run without modifying code.

Consult the module-level README files and Dockerfiles under each folder for deployment details.
   
