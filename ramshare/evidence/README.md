# Evidence Inbox (Local-Only)

Drop any files you want ingested here:
- `ramshare/evidence/inbox/`

This folder is gitignored (local-only). The ingestion pipeline will scan it for:
- PDFs (`.pdf`)
- HTML files (`.html`)
- Plain text / markdown (`.txt`, `.md`)

How it flows:
1. You drop a file into `ramshare/evidence/inbox/`.
2. (Optional) Run `scripts/watch-evidence.ps1` to auto-ingest on changes.
3. Ingestion writes extracted text into `ramshare/notes/raw/` (gitignored) and generates task stubs in `ramshare/agent-tasks/` (gitignored).
4. Distillation writes curated keepers into `ramshare/notes/distilled/` (commit these).

Evidence integrity:
- `trade_intent_log.jsonl` entries are hash-chained and HMAC-signed (see `scripts/evidence_chain.py`).
- Verification tool: `python C:\gemini\scripts\verify_evidence_chain.py`
- Optional immediate sink:
  - set `EVIDENCE_SINK_PATH` for append-only mirror on another disk/share
  - set `EVIDENCE_SINK_URL` to POST each entry to a remote collector
