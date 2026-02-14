# Learning Pipeline (3 Speeds)

This repo treats "learning" as a pipeline with three speeds:

## Instant (Context)
- Build a short "context pack" for the current task by retrieving relevant snippets from:
  - `ramshare/notes/distilled/`
  - `ramshare/notes/raw/` (generated)
- Output lives in: `ramshare/learning/context/current.md` (gitignored).

## Tactical (Memory)
- Store durable lessons and facts that should influence future work:
  - `ramshare/learning/memory/lessons.md` (committable)
- Optional: push distilled notes into the running Memory MCP server (knowledge graph) for fast recall.

## Structural (Preferences)
- Record approvals/rejections into a dataset so you can later fine-tune / DPO externally.
- This repo only provides storage scaffolding (no weight updates).

