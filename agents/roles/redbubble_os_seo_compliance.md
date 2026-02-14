## Role
Redbubble OS: SEO + Compliance

## Mission
Produce reusable SEO templates and a compliance workflow for manual Redbubble uploads.

## Inputs
- Niche seed: `{{NICHE}}`
- Optional concept backlog:
  - `.agent-jobs/{{RUN_ID}}/out/strategy_niche_scout/concept_backlog.json`

## Outputs
Write:
- `{{OUT_ROLE_DIR}}/seo_templates.md` (Markdown)
- `{{OUT_ROLE_DIR}}/tag_packs.md` (Markdown with tag packs in code blocks as newline-separated lists)
- `{{OUT_ROLE_DIR}}/compliance_workflow.md` (Markdown)
- `{{OUT_ROLE_DIR}}/tracking_schema.json` (STRICT JSON; minimal schema for designs + metadata + upload status)

## Tooling
- Reference:
  - `scripts/rb_ip_guard.py`
  - `data/redbubble/ip_risk_terms.txt`

## Constraints
- No keyword stuffing; keep metadata non-spammy.
- No automation of upload workflows; user uploads manually.

## Definition Of Done
- 5 title templates + 5 description templates.
- 6 tag packs (25-40 tags each), lowercase, no commas.
- Compliance workflow includes negative keyword seed list (30).
- Tracking schema is actionable (CSV/SQLite-friendly).

## Failure Handling
- If niche unclear, infer a reasonable sub-focus and document assumptions.

## Task
1) Title templates (5) and description templates (5).
2) 6 reusable tag packs (25-40 tags each), lowercase, no commas.
3) Compliance workflow + negative keyword seed list (30 items).
4) Data model: minimal schema for tracking designs + metadata + upload status.
