from __future__ import annotations

import os
from typing import Any, Dict

from mcp.server import FastMCP

app = FastMCP("document-loader")


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="ignore") as handle:
        return handle.read()


def _read_pdf(path: str) -> str:
    try:
        import pypdf
    except Exception as exc:
        raise RuntimeError("pypdf not installed; cannot read PDF") from exc
    reader = pypdf.PdfReader(path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n".join(parts)


@app.tool()
def load_document(path: str) -> Dict[str, Any]:
    """Load a document from disk and return text content."""
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        text = _read_pdf(path)
    else:
        text = _read_text(path)
    return {
        "path": path,
        "chars": len(text),
        "content": text,
    }


if __name__ == "__main__":
    app.run()
