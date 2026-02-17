from __future__ import annotations

import argparse
import hashlib
import json
import ipaddress
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse
from pathlib import Path
from typing import Any


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def safe_slug(url: str) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "_", url.strip())[:80].strip("_")
    return s or "url"


def hostname(url: str) -> str:
    try:
        u = urlparse(url)
        return (u.hostname or "").lower().strip(".")
    except Exception:
        return ""


def scheme(url: str) -> str:
    try:
        return (urlparse(url).scheme or "").lower()
    except Exception:
        return ""


def domain_allowed(host: str, allow: list[str], deny: list[str]) -> tuple[bool, str]:
    h = (host or "").lower().strip(".")
    if not h:
        return False, "missing hostname"

    for d in deny:
        d = d.lower().strip(".")
        if not d:
            continue
        if h == d or h.endswith("." + d):
            return False, f"denied domain: {d}"

    if not allow:
        return True, ""

    for a in allow:
        a = a.lower().strip(".")
        if not a:
            continue
        if h == a or h.endswith("." + a):
            return True, ""

    return False, "not in allowlist"


def host_is_private_or_local(host: str) -> tuple[bool, str]:
    h = (host or "").lower().strip(".")
    if not h:
        return True, "missing hostname"
    if h in ("localhost",):
        return True, "localhost blocked"
    if h.endswith(".local"):
        return True, ".local blocked"
    # Block direct IPs that are private, loopback, link-local, etc. (SSRF guardrail)
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


def fetch(url: str, *, timeout_s: int, max_bytes: int) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "gemini-op-webfetch/1.0 (+https://github.com/brokenbartender/GEMOP)",
            "Accept": "text/html,application/json,text/plain;q=0.9,*/*;q=0.1",
        },
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read(max_bytes + 1)
            truncated = len(raw) > max_bytes
            if truncated:
                raw = raw[:max_bytes]
            ctype = str(resp.headers.get("Content-Type") or "")
            return {
                "ok": True,
                "url": url,
                "status": int(getattr(resp, "status", 200) or 200),
                "content_type": ctype,
                "bytes": len(raw),
                "truncated": truncated,
                "sha256": sha256_bytes(raw),
                "duration_s": round(time.time() - t0, 3),
                "body_bytes": raw,
            }
    except urllib.error.HTTPError as e:
        return {"ok": False, "url": url, "status": int(getattr(e, "code", 0) or 0), "error": f"HTTPError: {e}", "duration_s": round(time.time() - t0, 3)}
    except Exception as e:
        return {"ok": False, "url": url, "status": 0, "error": f"{type(e).__name__}: {e}", "duration_s": round(time.time() - t0, 3)}


INJECTION_PATTERNS = [
    r"(?i)\bignore (all|any|the) (previous|prior) instructions\b",
    r"(?i)\byou are (now|no longer)\b",
    r"(?i)\b(system prompt|developer message|hidden instructions)\b",
    r"(?i)\bBEGIN (SYSTEM|DEVELOPER) PROMPT\b",
    r"(?i)\bdo not (disclose|reveal)\b.*\b(prompt|instructions)\b",
]


def strip_prompt_injection(text: str) -> tuple[str, int]:
    lines = text.splitlines()
    out: list[str] = []
    removed = 0
    for ln in lines:
        hit = False
        for pat in INJECTION_PATTERNS:
            if re.search(pat, ln):
                hit = True
                break
        if hit:
            removed += 1
            continue
        out.append(ln)
    return "\n".join(out).strip(), removed


def html_to_text(b: bytes) -> str:
    try:
        s = b.decode("utf-8", errors="ignore")
    except Exception:
        s = str(b)
    s = re.sub(r"(?is)<script.*?>.*?</script>", " ", s)
    s = re.sub(r"(?is)<style.*?>.*?</style>", " ", s)
    s = re.sub(r"(?is)<[^>]+>", " ", s)
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def main() -> int:
    ap = argparse.ArgumentParser(description="Fetch a set of URLs (safe, cached) and write sources.json/sources.md.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--urls", default="", help="Comma-separated URLs to fetch.")
    ap.add_argument("--urls-file", default="", help="File containing one URL per line.")
    ap.add_argument("--timeout-s", type=int, default=20)
    ap.add_argument("--max-bytes", type=int, default=400_000)
    ap.add_argument("--rate-limit-ms", type=int, default=500)
    ap.add_argument("--allow-domains", default="", help="Comma-separated domain allowlist (suffix match). Empty=allow all.")
    ap.add_argument("--deny-domains", default="", help="Comma-separated domain denylist (suffix match).")
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    state_dir = run_dir / "state"
    cache_dir = state_dir / "web_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)

    urls: list[str] = []
    if args.urls:
        urls += [u.strip() for u in args.urls.split(",") if u.strip()]
    if args.urls_file:
        p = Path(args.urls_file)
        if not p.is_absolute():
            p = (run_dir / p).resolve()
        if p.exists():
            for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
                ln = ln.strip()
                if ln and not ln.startswith("#"):
                    urls.append(ln)

    urls = list(dict.fromkeys(urls))
    allow = [d.strip() for d in str(args.allow_domains).split(",") if d.strip()]
    deny = [d.strip() for d in str(args.deny_domains).split(",") if d.strip()]
    results: list[dict[str, Any]] = []
    md_lines: list[str] = []
    md_lines.append("# Sources (Fetched)")
    md_lines.append("")
    md_lines.append(f"generated_at: {time.time()}")
    md_lines.append("")

    for idx, url in enumerate(urls, start=1):
        sch = scheme(url)
        host = hostname(url)
        if sch not in ("http", "https"):
            r = {"ok": False, "url": url, "status": 0, "error": f"disallowed scheme: {sch or 'unknown'}", "duration_s": 0.0}
        else:
            priv, why_priv = host_is_private_or_local(host)
            if priv:
                r = {"ok": False, "url": url, "status": 0, "error": f"blocked url ({host}): {why_priv}", "duration_s": 0.0}
            else:
                okd, why = domain_allowed(host, allow=allow, deny=deny)
                if not okd:
                    r = {"ok": False, "url": url, "status": 0, "error": f"blocked url ({host}): {why}", "duration_s": 0.0}
                else:
                    r = fetch(url, timeout_s=int(args.timeout_s), max_bytes=int(args.max_bytes))
        body = r.pop("body_bytes", b"") if isinstance(r, dict) else b""
        if r.get("ok") and body:
            slug = safe_slug(url)
            dst = cache_dir / f"{idx:03d}_{slug}.bin"
            dst.write_bytes(body)
            r["cache_path"] = str(dst)
            txt_raw = html_to_text(body)
            txt, removed = strip_prompt_injection(txt_raw)
            r["text_preview"] = txt[:800]
            md_lines.append(f"## [{idx}] {url}")
            md_lines.append("")
            md_lines.append(f"- status: {r.get('status')}")
            md_lines.append(f"- content_type: {r.get('content_type')}")
            md_lines.append(f"- sha256: `{r.get('sha256')}`")
            md_lines.append(f"- prompt_injection_lines_removed: {removed}")
            md_lines.append("")
            md_lines.append("```text")
            md_lines.append(txt[:2000])
            md_lines.append("```")
            md_lines.append("")
        else:
            md_lines.append(f"## [{idx}] {url}")
            md_lines.append("")
            md_lines.append(f"- ok: false")
            md_lines.append(f"- error: {r.get('error')}")
            md_lines.append("")
        results.append(r)
        time.sleep(max(0, int(args.rate_limit_ms)) / 1000.0)

    (state_dir / "sources.json").write_text(json.dumps({"urls": urls, "results": results, "generated_at": time.time()}, indent=2), encoding="utf-8")
    (state_dir / "sources.md").write_text("\n".join(md_lines).rstrip() + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "count": len(urls)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
