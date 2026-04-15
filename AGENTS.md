# AGENTS.md

## Project

ML pipeline for crop classification on AWS. Python 3.10+, managed with `uv`.

## Pipeline flow

```
Lambda (polygon crawl)          Fargate Spot              SageMaker Processing        SageMaker Processing
   UPRA API ──────────►  polygons JSON ──────►  raw/ (satellite imagery) ──────►  processed/ ──────►  Feature Store
                               │                    │                                  │                    │
                        crawl geoservicios     odc-stac extracts          silver: noise reduction,    gold: feature enrichment,
                                               pixel data from              cloud masking, time          derived features,
                                               public S3 + polygons         range adjustment            label from UPRA API
```

1. **Lambda** crawls UPRA geoservicios API, outputs polygon geometries
2. **Fargate Spot** reads polygons + pulls satellite imagery from public S3 (odc-stac), writes to `raw/`
3. **SageMaker Processing (silver)** reads `raw/`, applies noise reduction, cloud masking, time range adjustment; writes to `processed/`
4. **SageMaker Processing (gold)** reads `processed/`, enriches features, re-crawls UPRA API for labels, writes to Feature Store
5. **Step Functions** orchestrates the full pipeline

After step 4, the acquisition + dataset prep pipeline is complete — ready for training.

## Structure

- `src/processing/` — data processing package
- `src/training/` — model training package
- `infra/` — Terraform AWS infrastructure (root module, calls submodules)
- `infra/iam/` — IAM module (one role per file, detached policies in `policies.tf`)
- `workflows/` — Step Functions definitions

## IAM roles

| Role | Belongs to | Can do |
|---|---|---|
| `fargate-image-copy` | Fargate task | Write `raw/`, read public S3 |
| `lambda-polygon-crawl` | Lambda | HTTP calls to UPRA API, CloudWatch Logs |
| `ecs-task-execution` | ECS agent | Pull ECR images, write CloudWatch Logs |
| `sagemaker-processing-silver` | SageMaker | Read `raw/`, write `processed/` |
| `sagemaker-processing-gold` | SageMaker | Read `processed/`, write Feature Store |
| `step-functions` | Step Functions | Invoke Lambda, run ECS/SageMaker, PassRole |

S3 bucket prefixes follow medallion architecture: `raw/` (bronze), `processed/` (silver), Feature Store (gold).

## Commands

- `uv sync` — install dependencies and sync virtual environment
- `uv add <pkg>` — add a dependency
- `uv run python -m <module>` — run a Python module in the venv
- `uv run pytest` — run tests (once configured)
- `cd infra && terraform validate` — validate TF config

## Build

- Build system: `hatchling`
- Wheel packages: `src/processing`, `src/training`
- Python: `>=3.10` (pinned to 3.10.15 in `.python-version`)

## Remote

`origin` → `git@github.com:JuanJoZP/crop-classification-pipeline.git`