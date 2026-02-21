# Redbubble Concept Brief Schema (v1)

Use this schema when generating concept briefs for the Redbubble workflow.

## Required Fields

- `concept_id`: short stable id (`rb_<slug>_<nnn>`)
- `theme`: high-level niche/theme
- `audience`: target buyer segment
- `intent`: buyer intent (`gift`, `self-expression`, `hobby`, `event`)
- `visual_direction`: concise art direction
- `palette`: color guidance (or `black_white` for line-art)
- `composition`: layout notes (centered/stacked/badge/etc.)
- `prompt`: generation prompt text
- `negative_prompt`: disallowed traits/artifacts/IP
- `products`: target products (`tshirt`, `sticker`, etc.)
- `size_profile`: output profile (`4500x5400_tshirt`, `5000x5000_sticker`)
- `seo`: object with `title`, `tags`, `description`
- `risk`: object with `ip_risk_score` (`low|medium|high`) and `flags` array

## Optional Fields

- `series`: series name for grouped launches
- `variant_of`: parent concept id
- `trend_evidence`: list of URLs or short notes
- `quality_gate`: object with `line_density_target`, `alpha_required`, `min_resolution`

## Example

```json
{
  "concept_id": "rb_michigan_linework_001",
  "theme": "Michigan heritage line art",
  "audience": "local pride buyers",
  "intent": "gift",
  "visual_direction": "minimal black-and-white continuous line drawing",
  "palette": "black_white",
  "composition": "single centered emblem with generous negative space",
  "prompt": "Minimal vector-like line-art emblem inspired by Michigan heritage...",
  "negative_prompt": "logo, trademarked characters, celebrity likeness, watermark, blurry",
  "products": ["tshirt", "sticker"],
  "size_profile": "4500x5400_tshirt",
  "seo": {
    "title": "Michigan Linework Heritage Tee",
    "tags": ["michigan", "line-art", "heritage", "minimalist"],
    "description": "Clean monochrome linework inspired by Michigan heritage."
  },
  "risk": {
    "ip_risk_score": "low",
    "flags": []
  }
}
```
