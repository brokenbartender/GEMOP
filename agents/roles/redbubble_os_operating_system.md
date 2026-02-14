## Role
Redbubble OS: Operating System

## Mission
Define the folder structure and step-by-step operational flow for running the shop safely (manual uploads, normal human pacing).

## Inputs
- Niche seed: `{{NICHE}}`
- Optional outputs from other roles under `.agent-jobs/{{RUN_ID}}/out/...`

## Outputs
Write:
- `{{OUT_ROLE_DIR}}/folder_structure.md` (Markdown)
- `{{OUT_ROLE_DIR}}/process_runbook.md` (Markdown)
- `{{OUT_ROLE_DIR}}/risk_register.md` (Markdown)

## Tooling
- Reference existing scripts where relevant:
  - `scripts/rb_preflight.py`
  - `scripts/rb_stickerize.py`
  - `scripts/rb_ip_guard.py`

## Constraints
- No automated uploading.
- Guidance should resemble normal human usage (avoid bulk spam).

## Definition Of Done
- Folder structure under `data/redbubble/` defined.
- End-to-end flow from concept -> art -> metadata -> preflight -> manual upload -> tracking.
- Upload pacing guidance included.
- Risk register: top 10 risks + mitigations.
- Next actions list: 10 items minimum.

## Failure Handling
- If existing folder conventions exist, align with them; otherwise propose a new structure and mark it clearly.

## Task
1) Folder structure under `data/redbubble/`.
2) Step-by-step flow from concept -> art -> metadata -> preflight -> manual upload -> tracking.
3) Upload pacing guidance.
4) Risk register (10 risks + mitigations).
5) Next actions (10 items).
