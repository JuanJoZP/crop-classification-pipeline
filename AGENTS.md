# AGENTS.md

## Project

ML pipeline for crop classification on AWS. Python 3.12+, managed with `uv`.

## Structure

- `src/processing/` — data processing package
- `src/training/` — model training package
- `infra/` — AWS infrastructure definitions
- `workflows/` — workflow/pipeline orchestration

## Commands

- `uv sync` — install dependencies and sync virtual environment
- `uv add <pkg>` — add a dependency
- `uv run python -m <module>` — run a Python module in the venv
- `uv run pytest` — run tests (once configured)

## Build

- Build system: `hatchling`
- Wheel packages: `src/processing`, `src/training`
- Python: `>=3.10` (pinned to 3.10.15 in `.python-version`)

## Remote

`origin` → `git@github.com:JuanJoZP/crop-classification-pipeline.git`