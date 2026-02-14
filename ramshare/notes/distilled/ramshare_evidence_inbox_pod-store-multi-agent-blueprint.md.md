# POD Multi-Agent Store Blueprint (Mapping to gemini-op)

## Summary
- This document is a phase-based blueprint for running a print-on-demand store via many narrow agents (research, design, listing/SEO, marketing, fulfillment, customer service, risk/compliance, scaling, and meta-governance).
- The key pattern is: scheduled data collection -> transform -> decision -> execute -> measure -> loop (plus “kill switch” and cost control).
- It assumes lots of external integrations (platform APIs, scraping, image tools, ad platforms), which makes credentials, rate limits, ToS risk, and audit logging first-class.
- It needs clear “ownership boundaries”: which agent can read/write which systems, and which actions require human approval.
- The Phase 10 “meta” agents (manager, restart, cost controller, kill switch) are the control plane; everything else is workload.

## Gemini-op Implications (prioritized)
- P0: Treat this as a **multi-agent control-plane design spec** and implement the control-plane primitives first:
  - Scheduling, notification, logging/audit, cost/budget caps, and a global kill switch.
  - Strong secrets hygiene (no tokens in files/logs) and per-profile least privilege.
- P0: Split capabilities via **profiles** so “read-only research” is separate from “posting/updating/ordering”:
  - Example profiles: `research` (read + index), `browser` (interactive browsing), `ops` (platform writes), `full` (rare, break-glass).
- P1: Use the **evidence inbox** pattern for all “daily reports” and “agent outputs”:
  - Drop reports/artifacts into `ramshare/evidence/inbox/` so they auto-ingest, index, and queue for distillation.
- P1: Add structured “job templates” (one per agent type) so work is repeatable:
  - Inputs, outputs, data sources, expected run frequency, and allowed tools.
- P2: Add policy enforcement for high-risk actions:
  - “No scraping unless explicitly enabled”, “no posting unless human-approved”, “no ad spend changes above threshold”, etc.

## Mapping to This Repo
- Profiles: `profiles/config.*.toml`
  - Use profiles to enforce “which phase(s) are allowed to run”.
- Daemons: `start-daemons.ps1`, `mcp-daemons/`
  - Keep “memory + semantic search” always-on for recall; use browser tooling only when needed.
- Ingestion: `scripts/ingest-and-index.ps1`, `scripts/pull-resources.ps1`
  - Convert external documents and local evidence into searchable `notes/raw/`.
- Evidence inbox (auto-ingest): `ramshare/evidence/inbox/`, `scripts/watch-evidence.ps1`
- Distillation: `scripts/distill.ps1`, `ramshare/notes/distilled/`
- Governance staging: `ramshare/plan-updates/pending.md` (gitignored)

## Commands / Config Snippets
```powershell
# Start Gemini + background evidence ingestion watcher
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\gemini\start-gemini.ps1 -Profile research

# Drop a new “report” or “spec” for ingestion
#   C:\gemini\ramshare\evidence\inbox\<anything>.md

# Prepare prompts for distillation
powershell.exe -NoProfile -ExecutionPolicy Bypass -File C:\gemini\scripts\distill.ps1 -Profile research -Mode prepare -Match pod-store -UpdatePlan
```

## Risks / Gotchas
- Scraping marketplaces/social sites can violate ToS; prefer official APIs or explicit opt-in “scrape mode”.
- Copyright/trademark risk is central (catchphrases, viral audio, brand terms). A “Trademark Patrol” and “Banned Keyword Blocker” must run before publishing.
- Cost risk: image generation + transcription + ads can run away without hard caps and a kill switch.
- Credential sprawl: each integration should have its own token and least-privileged scope; log redaction is mandatory.

## Tags
- `multi-agent`, `automation`, `governance`, `scheduling`, `risk`, `cost`, `compliance`

