#!/usr/bin/env python
"""
Extract lightweight text from PDFs/HTML snapshots into plain text.

This exists to make downstream semantic indexing fast and deterministic:
- Avoid re-downloading or re-parsing large PDFs during interactive sessions.
- Keep extraction logic simple and dependency-light.
"""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path


def extract_pdf_text(src: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(src))
    out: list[str] = []
    for i, page in enumerate(reader.pages):
        try:
            txt = page.extract_text() or ""
        except Exception as e:  # pragma: no cover
            txt = f"[extract_text failed on page {i}: {e}]"
        out.append(txt)
    return "\n\n".join(out)


_RE_SCRIPT_STYLE = re.compile(r"(?is)<(script|style|noscript).*?>.*?</\\1>")
_RE_TAG = re.compile(r"(?is)<[^>]+>")
_RE_WS = re.compile(r"[ \\t\\f\\r]+")


def extract_html_text(src: Path) -> str:
    raw = src.read_text(encoding="utf-8", errors="replace")
    raw = _RE_SCRIPT_STYLE.sub(" ", raw)
    raw = _RE_TAG.sub(" ", raw)
    raw = html.unescape(raw)
    # Normalize whitespace while keeping line breaks.
    raw = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = []
    for line in raw.split("\n"):
        line = _RE_WS.sub(" ", line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", required=True, help="Input file path")
    ap.add_argument("--out", dest="outp", required=True, help="Output file path")
    args = ap.parse_args()

    src = Path(args.inp)
    dst = Path(args.outp)
    dst.parent.mkdir(parents=True, exist_ok=True)

    suf = src.suffix.lower()
    if suf == ".pdf":
        text = extract_pdf_text(src)
    elif suf in (".html", ".htm"):
        text = extract_html_text(src)
    else:
        raise SystemExit(f"Unsupported input type: {src}")

    dst.write_text(text, encoding="utf-8", errors="strict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

