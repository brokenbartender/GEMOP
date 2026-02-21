# Gemini OP (Market-Ready v1.0)

Gemini OP is an agentic workspace runner with a hardened PowerShell orchestrator and supporting scripts (Python + Node MCP daemons).

## The Sovereign Mythos (Generative Reality)

The system has been refined into a biological architecture that enables autonomous mission execution:

1.  **Sensory Layer (Nervous System):** `telluric_resonance.py` (hardware pulse) and `spirit_radio.py` (network latency) monitor the environment in real-time.
2.  **Immune Layer (Security):** `formal_verifier.py` (Neuro-symbolic safety) and `tesla_valve.py` (logic flow diode) prevent hallucinations and malicious mutations.
3.  **Cognitive Layer (Prefrontal Cortex):** `triad_orchestrator.ps1` manages multi-round design/implementation loops, offloading heavy reasoning to the cloud while maintaining deep memory locally via `gravity_well.py`.

## Project Prometheus (Self-Documenting API)

Gemini OP is now fully self-documenting. The Prometheus engine scans the repository and generates a unified reference:

```powershell
# Refresh the API Reference
python scripts/generate_api_docs.py
```
See [docs/API_REFERENCE.md](docs/API_REFERENCE.md) for the complete capability map.

## Hardware Optimization (i5 / 32GB RAM)

The system is specifically tuned for local/cloud hybrid execution:
- **Local Fallback:** `phi3:mini` is the definitive local model; `phi4` is blacklisted to prevent CPU timeouts.
- **Memory Density:** leverages 32GB RAM for semantic mass calculations via Gravity Well.
- **Console Compatibility:** All scripts are emoji-sanitized to prevent `UnicodeEncodeError` on Windows `cp1252` terminals.

## Quick start (Windows)

1) Install prerequisites:
- Git
- Python 3.x (ensure `python` is in PATH)
- Node.js + `npx`
- PowerShell (Windows PowerShell 5.1 or PowerShell 7)

2) Configure local settings:
- Copy `config.local.example.toml` to `config.local.toml`
- Set required secrets via environment variables referenced in the file (recommended)

3) Run the orchestrator on a run directory:
```powershell
pwsh .\scripts\triad_orchestrator.ps1 -RepoRoot (Resolve-Path .) -RunDir .\.agent-jobs\<your-run> -EnableCouncilBus
```

## One-line "Summon a Council" (Recommended)

Create a new run directory, auto-select skills from both `~/.codex/skills` and `~/.gemini/skills`, and run a multi-agent council:

```powershell
pwsh .\scripts\summon.ps1 -Task "Fix the failing tests and add coverage for the new feature" -Online
```

## The Sovereign Interface (Unified CLI)

Access all subsystems (Swarm, Finance, Commerce, Governance) through the single Sovereign Cortex entry point:

```powershell
# Summon a council
python scripts/sovereign.py summon "Research quantum computing trends" --online

# Run Finance Pipeline
python scripts/sovereign.py finance --run-now

# Launch Dashboard
python scripts/sovereign.py dashboard

# Self-Heal System
python scripts/sovereign.py recover
```

## Fidelity Integration (Free-first)

Use the new intake bridge to unify all Fidelity data paths into one pipeline:
`scripts\fidelity_intake.py` -> `portfolio_snapshot.json` -> `fidelity_profile` report.

### 1) Free + safest (CSV/manual export)
```powershell
python .\scripts\fidelity_intake.py csv --path C:\path\to\fidelity_positions.csv --account-id Z39213144 --run-profile
```

If you copied table text instead of CSV:
```powershell
python .\scripts\fidelity_intake.py raw --path C:\path\to\fidelity_positions.txt --account-id Z39213144 --run-profile
```

### 2) Aggregator proxy (JSON from a middle layer)
```powershell
python .\scripts\fidelity_intake.py json --path C:\path\to\aggregator_positions.json --account-id Z39213144 --run-profile
```

### 3) Optional browser adapter (higher maintenance risk)
This uses the existing Playwright adapter in `skill_fidelity_trader.py`.
```powershell
python .\scripts\fidelity_intake.py playwright --account-id Z39213144 --run-profile
```

### Quality controls
- Deep lead/event search is enabled in `fidelity_profile` (`search_depth=deep`).
- Source/recency filtering and diagnostics are included in output reports.
- You can enforce stricter source quality:
```powershell
python .\scripts\fidelity_intake.py csv --path C:\path\to\fidelity_positions.csv --account-id Z39213144 --min-source-trust-score 1 --run-profile
```

### Finance-focused council
```powershell
pwsh .\scripts\fidelity_council.ps1 -Task "Build tomorrow execution ticket from my Fidelity profile" -Online
```

## Finance Council Skillset (Modular)

This is a reusable finance capability inside the general multi-purpose app:
- `finance_council` skill composes six specialist agents:
`Technical Analyst`, `Fundamental Analyst`, `Sentiment Analyst`, `Risk Manager`, `Execution Trader`, `Chief of Staff`.
- It reads your snapshot + latest `fidelity_profile` leads, debates per symbol, applies risk veto logic, and emits a ranked action plan.
- Optional paper trade jobs can be generated for `fidelity_trader` (still paper-only by default).

### Run once from current snapshot
```powershell
python .\scripts\finance_council_run.py --account-id Z39213144 --run-now
```

### Ingest CSV then run finance council and emit paper tickets
```powershell
python .\scripts\finance_council_run.py --account-id Z39213144 --csv C:\path\to\positions.csv --emit-paper-jobs --max-paper-jobs 2 --run-now
```

### Launch an actual multi-agent council debate after deterministic prep
```powershell
python .\scripts\finance_council_run.py --account-id Z39213144 --launch-council --online --council-rounds 3 --run-now
```

## Theme Stock Research (Any Theme)

Use `market_theme_research` when you want discovery beyond your current holdings.
It supports any theme string, runs deep lead mining, excludes symbols you already hold, and returns:
- ranked candidate symbols (`buy_candidate` / `watch` / `avoid`)
- source-backed leads
- `1-day`, `1-week`, `1-month` execution plans

### Run theme research immediately
```powershell
python .\scripts\market_theme_run.py --theme "best ai micro investments for this week" --account-id Z39213144 --search-depth deep --max-candidates 12 --run-now
```

### Example with a different theme
```powershell
python .\scripts\market_theme_run.py --theme "small-cap cybersecurity stocks this week" --account-id Z39213144 --search-depth deep --max-candidates 10 --run-now
```

Outputs:
- Latest summary: `ramshare\strategy\market_theme_latest.json`
- Historical reports: `ramshare\evidence\reports\market_theme_<theme>_<timestamp>.json`

## Redbubble Art Pipeline (Free-First)

This app now includes a free default creation pipeline for POD assets:
- `trend_spotter` (free RSS trend pull)
- `product_drafter` (local line-art generation by default)
- `art_director` (quality gate + revision loop)
- `listing_generator` (SEO + IP risk filtering)
- `uploader` (mock publish receipt for execution testing)

### One-command run
```powershell
python .\scripts\redbubble_pipeline_run.py --theme "minimal geometric symbols for Michigan gifts" --run-now
```

### Art Syndicate Council (Trend -> Create -> Debate -> Revise -> Approve)
This runs a 5-role loop (Trend Hunter, Creative Director, Compliance Officer, Hype Man, Shop Manager),
prevents near-duplicates against your catalog cache, and keeps revising until council approval or max revisions.

```powershell
python .\scripts\art_syndicate_run.py --query "trendy spots in michigan 2026" --max-revisions 4 --max-candidates 6
```

Outputs:
- council report: `ramshare\evidence\reports\art_syndicate_*.json`
- duplicate catalog cache: `data\redbubble\shop_catalog_cache.json`
- approved listing (if pass): `ramshare\evidence\staging\listing_*.json`
- manual-safe upload receipt/packet: `ramshare\evidence\posted\live_*.json` + `ramshare\evidence\upload_packets\...`

### Train style from your existing artwork ZIP/folder
Use your current shop exports as a local style reference. This generates:
`data\redbubble\style_profile.json` used automatically by `product_drafter`.

```powershell
python .\scripts\rb_style_train.py --zip "C:\Users\codym\Downloads\drive-download-20260219T054136Z-1-001.zip"
```

Or from an already-extracted folder:
```powershell
python .\scripts\rb_style_train.py --dataset-dir "C:\path\to\art_folder"
```

### Run style calibration cycles + variety tests (recommended)
This performs iterative training cycles against your reference style metrics and updates
`style_profile.json` generator overrides for closer linework consistency across varied prompts.

```powershell
python .\scripts\rb_style_cycle.py --cycles 8 --zip "C:\Users\codym\Downloads\drive-download-20260219T054136Z-1-001.zip" --apply
```

You can test custom variety prompts:
```powershell
python .\scripts\rb_style_cycle.py --cycles 8 --themes "trendy bar downtown detroit,hidden coffee shop ann arbor,waterfall trail tahquamenon falls,beach campground michigan" --apply
```

The report is written to `ramshare\evidence\reports\rb_style_cycle_*.json`.

### Convert a real photo into your line-art style (iterative)
Use this when you want a specific real landmark/building transformed into your Redbubble-ready style.
It runs multiple parameter cycles, optimizes for structural fidelity + style targets, and exports:
- transparent master PNG (4500x5400)
- white preview PNG for visual review
- detailed scoring report JSON

```powershell
python .\scripts\rb_photo_to_style.py --image "C:\Users\codym\Downloads\Fox Theater.jpg" --cycles 14 --seed 7
```

You can also feed photo references directly through `product_drafter` via:
- `inputs.reference_image_path`

### Rigorous sellability harness + approved first upload packet
```powershell
python .\scripts\redbubble_profit_harness.py --theme "minimal geometric symbols for Michigan gifts" --variants 6 --approve-upload
```
This runs multiple variants, picks the top-scoring listing, and creates a manual-safe Redbubble upload packet.

### One-command: retrain style then run Art Syndicate
```powershell
python .\scripts\art_syndicate_run.py --query "trendy spots in michigan 2026" --style-cycles 8 --style-zip "C:\Users\codym\Downloads\drive-download-20260219T054136Z-1-001.zip" --max-revisions 4 --max-candidates 6
```

### Manual-safe upload packet output
- Receipt: `ramshare\evidence\posted\live_*.json`
- Packet folder: `ramshare\evidence\upload_packets\<timestamp>_<slug>\`
- Use `manual_steps.md` + `upload_manifest.json`; your only manual action is clicking Publish in Redbubble UI.

### Force free mode globally
```powershell
$env:GEMINI_OP_FREE_MODE="1"
$env:GEMINI_OP_ALLOW_PAID_ART="0"
$env:GEMINI_OP_ART_BACKEND="local_lineart"
```

### Use your logged-in Gemini CLI as cloud provider (no API key path)
```powershell
$env:GEMINI_OP_ENABLE_GEMINI_CLI_PROVIDER="1"
$env:GEMINI_OP_PREFER_GEMINI_CLI_PROVIDER="1"
$env:GEMINI_OP_GEMINI_CLI_MODEL="gemini-2.5-flash-lite"
```
This makes council cloud seats route to the authenticated `gemini` CLI first, with SDK/cloud and local fallbacks preserved.

### Optional local Stable Diffusion backend
If Automatic1111 is running locally:
```powershell
$env:SD_WEBUI_URL="http://127.0.0.1:7860"
python .\scripts\redbubble_pipeline_run.py --concept "vintage river city skyline" --image-backend sdwebui --run-now
```

### Upload mode
Default upload mode is account-safe packet generation:
```powershell
$env:REDBUBBLE_UPLOAD_MODE="manual_packet"
```
Legacy mock publish mode:
```powershell
$env:REDBUBBLE_UPLOAD_MODE="mock"
```

## Key scripts

- `scripts\smart_summon.ps1` — The primary entrypoint for multi-repo, autonomous tasks.
- `scripts\triad_orchestrator.ps1` — primary orchestrator engine.
- `scripts\event_horizon.py` — Schwarzschild-style pre-dispatch context-collapse guard.
- `scripts\hawking_emitter.py` — failure micro-summary emitter for terminated loops/tasks.
- `scripts\myth_runtime.py` — consolidated Phase VI plugin dispatcher (Hubble/Wormhole/Dark-Matter).
- `scripts\phase6_schema.py` — shared schema constants/validators for Phase VI task artifacts.
- `scripts\task_contract.py` — canonical task contract extraction (objective/constraints/deliverables/verification).
- `scripts\task_pipeline.py` — per-round planner/executor/verifier pipeline + deterministic ranking artifacts.
- `scripts\yeet.ps1` — Sovereign delivery tool (Verified Push).
- `scripts\slavic_recovery.ps1` — System healing and resurrection.

## Logging

The orchestrator writes a structured log file to the run directory by default:
- `triad_orchestrator.log`

Logs are sanitized to avoid accidental secret disclosure.
