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
- `src/lambdas/crawl_polygons/` — Lambda source for polygon crawl
- `infra/` — Terraform AWS root module (calls submodules)
- `infra/iam/` — IAM module (one role per file, 12 detached policies in `policies.tf`)
- `infra/modules/s3/` — S3 bucket with encryption, public access block, lifecycle rules
- `infra/modules/lambda/` — Generic Lambda module (zip + deploy, pip install, git SHA in description)
- `infra/modules/feature-store/` — SageMaker Feature Group + offline store (Glue catalog)
- `infra/budgets/` — AWS Budgets monthly cost alert
- `workflows/` — Step Functions definitions

## Infrastructure modules

| Module | Source | Creates |
|---|---|---|
| `s3` | `./modules/s3` | S3 bucket (versioning disabled, SSE-S3, public access blocked, lifecycle: `raw/` expires 7d, `processed/` expires 30d) |
| `iam` | `./iam` | 6 IAM roles + 12 detached policies scoped to bucket prefixes |
| `lambda_crawl_polygons` | `./modules/lambda` | Lambda function with pip install, zip deploy, git SHA |
| `feature_store` | `./modules/feature-store` | SageMaker Feature Group `crop-polygon-features` (5 features, offline store to S3 + Glue) |
| `budgets` | `./budgets` | AWS Budgets monthly alert ($1/mo default) |

## IAM roles

| Role | Belongs to | Can do |
|---|---|---|
| `fargate-image-copy` | Fargate task | Write `raw/`, read public S3 |
| `lambda-polygon-crawl` | Lambda | CloudWatch Logs (basic execution) |
| `ecs-task-execution` | ECS agent | Pull ECR images, write CloudWatch Logs |
| `sagemaker-processing-silver` | SageMaker | Read `raw/`, write `processed/` |
| `sagemaker-processing-gold` | SageMaker | Read `processed/`, write Feature Store + `feature-store/` prefix, Glue catalog, CloudWatch |
| `step-functions` | Step Functions | Invoke Lambda, run ECS/SageMaker, PassRole for ECS + SageMaker roles |

S3 bucket prefixes follow medallion architecture: `raw/` (bronze), `processed/` (silver), `feature-store/` (gold), Feature Store (gold).

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