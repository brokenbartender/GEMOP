## Context (RB Style Lab)

Goal:
- Learn, replicate, and innovate a cohesive minimalist black-and-white architectural line-art style based on a local reference dataset.

Inputs:
- `DatasetDir`: `{{DATASET_DIR}}`

Repo tools you may reference (do not duplicate logic):
- `scripts/analyze_png_lineart.py`
- `scripts/rb_preflight.py`
- `scripts/rb_stickerize.py`
- `scripts/marketplace_image_check.py`
- `data/marketplace_image_standards.json`
- `redbubble_system/gemini_brief.md` (concept schema reference)

Hard constraints:
- No stealth automation, login bypass, fingerprint spoofing, or automated uploading to Redbubble.
- Avoid trademarks/copyrighted characters and celebrity/public-figure likeness.

Marketplace reminders (high level; cite repo standards where applicable):
- Redbubble artwork caps: max 300MB, max 13,500px on a side; one-file covers all products at ~9075x6201px; use PNG for transparency (stickers/apparel).
- Etsy listing photos: >=2000px recommended; transparent PNG not supported (renders black); keep aspect ratios presentation-friendly.

## Run Paths

- Run dir: `.agent-jobs/{{RUN_ID}}`
- Shared outputs: `.agent-jobs/{{RUN_ID}}/out/shared/`
