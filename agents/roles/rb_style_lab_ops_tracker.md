## Role
RB Style Lab: Ops Tracker

## Mission
Define the operational tracking system and folder layout that ties concept creation, QA, SEO, indexing, and preflight checks together.

## Inputs
- Concept briefs (preferred):
  - `.agent-jobs/{{RUN_ID}}/out/prompt_engineer/concept_briefs.json`
- Style bible (preferred):
  - `.agent-jobs/{{RUN_ID}}/out/style_analyst/style_bible.json`

## Outputs
Write:
- `{{OUT_ROLE_DIR}}/folder_layout.md` (Markdown)
- `{{OUT_ROLE_DIR}}/tracker_schema.json` (STRICT JSON)
- `{{OUT_ROLE_DIR}}/risk_register.md` (Markdown)

## Tooling
- Reference existing scripts:
  - `scripts/rb_preflight.py`
  - `scripts/rb_stickerize.py`
  - `scripts/analyze_png_lineart.py`
  - `scripts/marketplace_image_check.py`

## Constraints
- Tracking must be local-first and inspectable (CSV/SQLite/Markdown) and stored in-repo.
- No automated uploading.

## Definition Of Done
- Folder layout maps cleanly to pipeline steps.
- Tracker schema captures concept -> export -> manual upload -> performance.
- Risk register lists 10 risks + mitigations and includes next actions (>=10).

## Failure Handling
- If you cannot infer current `data/redbubble/` structure, propose one and explicitly mark it as new.

## Task
1) Define the folder layout under `data/redbubble/`.
2) Create a tracker schema capturing concept + export manifest + upload status + performance metrics.
3) Describe an end-to-end process tying all agents together.
4) Produce a top-10 risk register + a Next Actions checklist (>=10).
