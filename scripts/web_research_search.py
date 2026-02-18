from __future__ import annotations

import argparse
import ipaddress
import json
import re
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

try:
    # New package name (preferred).
    from ddgs import DDGS  # type: ignore
except Exception:  # pragma: no cover
    # Back-compat for older installs.
    from duckduckgo_search import DDGS  # type: ignore


def _safe_slug(s: str) -> str:
    t = re.sub(r"[^A-Za-z0-9]+", "_", (s or "").strip())[:80].strip("_")
    return t or "query"


def _hostname(url: str) -> str:
    try:
        u = urlparse(url)
        return (u.hostname or "").lower().strip(".")
    except Exception:
        return ""


def _scheme(url: str) -> str:
    try:
        return (urlparse(url).scheme or "").lower()
    except Exception:
        return ""


def _host_is_private_or_local(host: str) -> tuple[bool, str]:
    h = (host or "").lower().strip(".")
    if not h:
        return True, "missing hostname"
    if h in ("localhost",):
        return True, "localhost blocked"
    if h.endswith(".local"):
        return True, ".local blocked"
    try:
        ip = ipaddress.ip_address(h)
        if ip.is_private:
            return True, "private ip blocked"
        if ip.is_loopback:
            return True, "loopback ip blocked"
        if ip.is_link_local:
            return True, "link-local ip blocked"
        if ip.is_multicast:
            return True, "multicast ip blocked"
        if ip.is_reserved:
            return True, "reserved ip blocked"
    except Exception:
        pass
    return False, ""


def _read_queries(args: argparse.Namespace, *, run_dir: Path) -> list[str]:
    queries: list[str] = []
    if args.query:
        queries.append(str(args.query).strip())
    if args.query_file:
        p = Path(args.query_file)
        if not p.is_absolute():
            p = (run_dir / p).resolve()
        if p.exists():
            for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    queries.append(ln)
    # Stable de-dupe preserving order.
    out: list[str] = []
    seen = set()
    for q in queries:
        if q and q not in seen:
            out.append(q)
            seen.add(q)
    return out


def _search_ddg(query: str, max_results: int) -> list[dict[str, Any]]:
    with DDGS() as ddgs:
        return list(ddgs.text(query, max_results=max_results))


def _iter_urls(results: Iterable[dict[str, Any]]) -> Iterable[str]:
    for r in results:
        href = r.get("href") or r.get("url") or ""
        href = str(href).strip()
        if href:
            yield href


def main() -> int:
    ap = argparse.ArgumentParser(description="DDG search -> write run_dir/state/research_urls.txt (safe URL list).")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--query", default="")
    ap.add_argument("--query-file", default="")
    ap.add_argument("--max", type=int, default=8)
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    queries = _read_queries(args, run_dir=run_dir)
    if not queries:
        (state_dir / "research_urls.txt").write_text("", encoding="utf-8")
        print(json.dumps({"ok": False, "error": "no_query"}, indent=2))
        return 2

    max_results = max(1, min(int(args.max or 8), 25))
    all_results: list[dict[str, Any]] = []
    urls: list[str] = []

    for q in queries:
        res = _search_ddg(q, max_results=max_results)
        all_results.extend(res)
        for u in _iter_urls(res):
            sch = _scheme(u)
            host = _hostname(u)
            if sch not in ("http", "https"):
                continue
            priv, _why = _host_is_private_or_local(host)
            if priv:
                continue
            urls.append(u)

    # Stable de-dupe preserving order.
    out_urls: list[str] = []
    seen = set()
    for u in urls:
        if u not in seen:
            out_urls.append(u)
            seen.add(u)

    (state_dir / "research_urls.txt").write_text("\n".join(out_urls).rstrip() + ("\n" if out_urls else ""), encoding="utf-8")
    (state_dir / "research_results.json").write_text(
        json.dumps(
            {
                "ok": True,
                "queries": queries,
                "max_results": max_results,
                "count_urls": len(out_urls),
                "results": all_results,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "queries": queries, "count_urls": len(out_urls)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
