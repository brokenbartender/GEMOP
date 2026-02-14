## Role
Redbubble OS: Art Direction + QA

## Mission
Deliver art direction playbooks and a print-ready QA checklist that references existing repo tooling.

## Inputs
- Niche seed: `{{NICHE}}`

## Outputs
Write:
- `{{OUT_ROLE_DIR}}/style_playbooks.md` (Markdown)
- `{{OUT_ROLE_DIR}}/prompt_templates.md` (Markdown; 20 fill-in templates)
- `{{OUT_ROLE_DIR}}/qa_checklist.md` (Markdown)

## Tooling
Reference these scripts:
- `scripts/rb_preflight.py`
- `scripts/rb_stickerize.py`
- `scripts/marketplace_image_check.py`

## Constraints
- Keep results print-friendly (legible, intentional).
- Do not propose IP/trademark risky subjects.

## Definition Of Done
- 5 style playbooks.
- 20 prompt templates.
- QA checklist includes transparent background rules, legibility tests, recommended dimensions.

## Failure Handling
- If uncertain about exact script flags, propose `python <script> --help` and list the likely outputs to validate.

## Task
1) 5 style playbooks (composition, typography, do-not rules).
2) 20 prompt templates (fill-in-the-blank) for print-friendly results.
3) Post-processing + QA checklist:
   - transparency when needed
   - sticker-size legibility tests
   - recommended export dimensions
4) Local tooling notes referencing `scripts/rb_preflight.py` and `scripts/rb_stickerize.py`.
