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

## Silver step — noise reduction, cloud masking, time range adjustment

**Input**: `raw/` (NetCDF file per parcel, downloaded from odc-stac; legacy zarr supported for backward compat)
**Output**: `processed/` (NetCDF file per parcel)

### Processing stages per parcel

| Stage | Description |
|---|---|
| 1. Band rename | `swir16` → `swir1` |
| 2. veg_index | `(nir - red) / (nir + red + swir1)` |
| 3. AOI mask | Polygon bounds + `aoi_padding` (meters) |
| 4. Clear pixels | Cloud mask via SCL classes + `clouds_padding` (meters) |
| 5. Stack + dropna | Stack lat/lon → pixel dim, drop pixels with no veg_index |
| 6. Clean (PhenolopyCleaner) | Remove temporal outliers, smooth noise |
| 7. Season filter (MainSeasonFilter) | Filter time range by crop planting/harvest window |
| 8. Drop time | Drop timesteps with no valid veg_index |
| 9. Spectral indexes | NDVI, EVI, SAVI, etc. (config: `indexes`) |
| 10. Phenometrics | Phenological metrics (if `calc_phenometrics: true`) |
| 11. Drop vars + transpose | Drop `spatial_ref`, `scl`; transpose to `(pixel, time)` |

### Sidecar metadata

- `processing_silver_metadata`: `{git_sha, timestamp, data_key, bronze_key}`
- Inherits `processing_bronze_metadata` from bronze

### Config (`silver/config.py`)

| Key | Description |
|---|---|
| `aoi_padding` | Meters to pad polygon bounds (default: 100) |
| `clouds_padding` | Meters to buffer cloud masks (default: 300) |
| `cloud_mask_scl_keep_classes` | SCL classes to keep as clear (default: `[3, 7, 10, 11]`) |
| `indexes` | List of spectral indexes to compute (default: `["ndvi", "evi", "savi"]`) |
| `calc_phenometrics` | Whether to compute phenological metrics (default: `false`) |

### Data format

Files are stored as NetCDF (`.nc`) per parcel. Legacy `.zarr` stores are supported for backward compatibility — readers try `.nc` first, then fall back to `.zarr`.

```
raw/{pid}.nc           (bronze — satellite imagery)
processed/{pid}.nc     (silver — cleaned + spectral indexes)
```

Sidecar metadata uses `data_key` (e.g. `raw/{pid}.nc` or `processed/{pid}.nc`). Legacy sidecars with `zarr_key` are still readable.

```
processed/{pid}.nc
├── veg_index     (pixel, time)
├── ndvi          (pixel, time)
├── evi           (pixel, time)
├── ...           (other spectral indexes)
└── {raw bands}  (pixel, time)
```

## Gold step — feature enrichment, normalization, label extraction

**Input**: `processed/` (NetCDF file per parcel; legacy zarr supported for backward compat)
**Output**: `feature-store/` (parquet + metadata JSON)

### Processing stages

| Stage | Description |
|---|---|
| 1. Discover parcels | List all parcels in `processed/` |
| 2. Lineage check | Skip if silver/bronze git SHA unchanged |
| 3. Compute global scalers | Fit `StandardScaler` or `MinMaxScaler` per variable across all parcels |
| 4. Normalize per parcel | Apply global scaler to mean time series per parcel |
| 5. Extract label | Map `cultivo`: `arroz` → 0, `papa` → 1, `maiz` → 2 |
| 6. Write parquet | One row per parcel with metadata + normalized time series |
| 7. Write metadata | JSON with git SHA, scalers, normalization method, lineage |

### Output schema (parquet)

| Column | Type | Description |
|---|---|---|
| `polygon_id` | string | Parcel ID (from sidecar) |
| `cultivo` | string | Crop name |
| `departamen` | string | Department |
| `municipio` | string | Municipality |
| `year` | int | Year from service name |
| `semester` | int | Semester from service name (`s1`=1, `s2`=2) |
| `label` | int | Integer label (arroz=0, papa=1, maiz=2) |
| `n_timesteps` | int | Number of time steps after silver |
| `n_pixels` | int | Number of valid pixels |
| `{var}_normalized` | list[float] | Normalized mean time series per variable |

### Config (`gold/config.py`)

| Key | Description |
|---|---|
| `normalization_method` | `"zscore"` (StandardScaler) or `"minmax"` (MinMaxScaler) |

### S3 outputs

- **Data**: `feature-store/gold_timeseries_{timestamp}.parquet`
- **Metadata**: `feature-store/gold_timeseries_{timestamp}_metadata.json`

Metadata JSON includes:
```json
{
  "gold_git_sha": "...",
  "gold_timestamp": "...",
  "parquet_key": "feature-store/gold_timeseries_...",
  "n_parcels": N,
  "linaje": {"bronze_git_sha": "...", "silver_git_sha": "..."},
  "scalers": {"var": {"mean": ..., "std": ...}},
  "normalization_method": "zscore"
}
```

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