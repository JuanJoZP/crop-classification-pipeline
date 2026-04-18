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

## Lambda detail: `crawl_polygons`

The Lambda is dispatched by `event["action"]` (defaults to `"crawl_polygons"`):

| Action | Handler |
|---|---|
| `"crawl_polygons"` | `endpoints/crawl_polygons.handle()` |
| `"list_municipalities"` | `endpoints/list_municipalities.handle()` |

### UPRA API (ArcGIS)

Base URL: `https://geoservicios.upra.gov.co/arcgis/rest/services/MonitoreoCultivos/{service}/MapServer/0/query`

Services follow the pattern `{crop}_{year}_s{semester}` (e.g. `arroz_2021_s1`), defined in `VALID_PERIODS`. **Important**: the Lambda `periodos` parameter takes **years** (e.g. `"2024"`), not the service names themselves. The Lambda internally maps each year to its corresponding services via `VALID_PERIODS` and queries all of them.

#### Endpoint A — Polygon query (`crawl_polygons` action)

| Param | Value |
|---|---|
| `where` | `municipio='{municipality}'` |
| `outFields` | `objectid,cultivo,municipio,departamen,periodo,intervalo` |
| `f` | `geojson` |
| `outSR` | `4326` |

Returns ArcGIS GeoJSON `FeatureCollection` with `features[].properties = {objectid, cultivo, municipio, departamen, periodo, intervalo}` and `features[].geometry = Polygon`.

Transform: each Feature is flattened into `{...properties, geometry, service, acquisition_date}`, then reassembled via `rows_to_geojson()` back into a GeoJSON FeatureCollection with two extra properties per feature: `service` (ArcGIS service name) and `acquisition_date` (ISO UTC timestamp), plus a top-level `"count"`.

#### Endpoint B — Distinct municipalities (`list_municipalities` action)

| Param | Value |
|---|---|
| `where` | `1=1` |
| `outFields` | `municipio,departamen` |
| `returnDistinctValues` | `true` |
| `returnGeometry` | `false` |
| `f` | `json` |

Returns ArcGIS JSON `FeatureSet` with `features[].attributes = {municipio, departamen}`. Called once per service for the given crop, deduplicated by `(municipio, departamen)`, sorted by `(departamen, municipio)`.

### S3 outputs

#### `crawl_polygons` action

- **Key**: `polygons/crawl_polygons_{timestamp}.json` (timestamp format `%Y%m%dT%H%M%SZ`)
- **Body**: GeoJSON FeatureCollection `{type, features: [{type: "Feature", geometry: {type: "Polygon", coordinates}, properties: {objectid, cultivo, municipio, departamen, periodo, intervalo, service, acquisition_date}}], count}`
- **Metadata**: `action=crawl_polygons`, `municipios=["..."]`, `periodos=["..."]`, `timestamp=...`

#### `list_municipalities` action

- **Key**: `polygons/list_municipalities_{timestamp}.json`
- **Body**: `{crop: "arroz", count: 42, municipalities: [{municipio, departamen}, ...]}`
- **Metadata**: `action=list_municipalities`, `crop=arroz`, `timestamp=...`

### Transformation summary

| Action | HTTP response → intermediate → S3 output |
|---|---|
| `crawl_polygons` | ArcGIS GeoJSON FeatureCollection → flat rows `{...properties, geometry, service, acquisition_date}` → GeoJSON FeatureCollection with extra `service` + `acquisition_date` properties + `count` |
| `list_municipalities` | ArcGIS JSON FeatureSet `features[].attributes` → deduplicated `{municipio, departamen}` list → `{crop, count, municipalities}` envelope |

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