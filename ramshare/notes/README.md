# Notes (Extracted + Distilled)

This is the local pipeline output for turning `ramshare/resources/` into searchable notes.

Folders:
- `raw/`: extracted plain text (generated; gitignored)
- `distilled/`: curated notes to keep (commit these)

Workflow:
1. Run `scripts/ingest-and-index.ps1` to refresh resources, extract text, and trigger indexing.
2. Use semantic search over the repo to find relevant passages in `raw/`.
3. Convert the useful bits into a small distilled note in `distilled/`.

Automation helpers:
- `scripts/health.ps1`: checks required daemons/deps for a given profile.
- `scripts/distill.ps1`:
  - `-Mode prepare` generates per-resource Gemini prompts into `ramshare/distill-prompts/` (gitignored)
  - `-Mode run` can run `gemini exec` to process those prompts non-interactively (requires Gemini CLI auth)
