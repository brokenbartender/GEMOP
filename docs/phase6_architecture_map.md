# Phase VI Architecture Map

## Scope

This document maps the live execution path for GEMOP and records where Phase VI cosmology controls are applied.

## Runtime Entry Points

- `scripts/summon.ps1`
- `scripts/triad_orchestrator.ps1`
- `scripts/agent_runner_v2.py`

## Control-Plane Lifecycle (Orchestrator)

1. Run bootstrap
- initialize run/state folders and mission anchor
- initialize ledger/meta and optional council bus
- optional tool registry + state rebuild

2. Pre-dispatch guards
- Event Horizon gate (`scripts/event_horizon.py`)
- Higgs mass signal (`scripts/higgs_field.py`)

3. Per-round pipeline
- optional web research ingest
- skill pack selection
- retrieval pack generation
- task contract extraction (`task_contract.py`)
- task pipeline generation (`task_pipeline.py`)
- prompt scaffold generation
- runner script generation
- agent execution + timeout handling
- supervisor scoring + state rebuild
- patch apply + verify pipeline
- mythology/physics hooks (Iolaus, Zhinan, Ren, Lotus, Gravity, Quantum, Telluric, etc.)
- adaptive concurrency update

4. Finalization
- learning summary and final scoring
- optional council reflection learner
- mana ranker
- threshold fail-closed check + exit

## Data Plane (Agent)

`scripts/agent_runner_v2.py` handles:
- provider routing and local/cloud tiering
- quota enforcement and cloud-seat policy
- local slot lock coordination
- escalation logging
- mock/test mode behavior

## State Artifacts

Primary run-state files under `<run_dir>/state`:
- `manifest.json`
- `world_state.md`
- `fact_sheet.md`
- `retrieval_pack_roundN.{json,md}`
- `supervisor_roundN.json`
- `verify_report.json`
- `event_horizon.json`
- `hawking_radiation.jsonl`
- `task_contract.json`
- `task_pipeline_roundN.json`
- `task_rank_roundN.json`
- `lifecycle_events.jsonl`

Bus artifacts under `<run_dir>/bus`:
- `messages.jsonl`
- `state.json`

## Phase VI Mapping

1. Context Collapse / Event Horizon
- Implemented:
  - `scripts/event_horizon.py`
  - pre-dispatch hook in `scripts/triad_orchestrator.ps1`
- Current behavior:
  - computes task mass and compares against context radius
  - splits oversized prompts into shards prior to dispatch

2. Data Lake Expansion / Hubble Drift
- In progress:
  - drift model + wormhole indexing scripts
  - retrieval integration path

3. Dead-End Evaporation / Hawking Radiation
- Implemented:
  - `scripts/hawking_emitter.py`
  - emission on Iolaus kill paths in `scripts/iolaus_cauterize.py`

4. Invisible Guardrails / Dark Matter Halo
- In progress:
  - halo profile generation and prompt injection path

## Known Cohesion Risks

- mythology hooks are still mostly orchestrator-inline (high coupling)
- constants/thresholds are distributed across scripts
- retrieval and long-memory strategy need unified drift governance

## Consolidation Target

Move toward one plugin runtime:
- `scripts/myth_runtime.py` as a single hook dispatcher
- shared config for physics/alignment constants
- one event schema for all lifecycle emissions

## Shared Schema

- `scripts/phase6_schema.py` is the canonical schema validator/constants module for:
  - `task_contract_roundN.json`
  - `task_pipeline_roundN.json`
  - `task_rank_roundN.json`
