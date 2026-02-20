from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
INBOX_DIR = REPO_ROOT / "ramshare" / "evidence" / "inbox"
POSTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "posted"
DISPATCHER = REPO_ROOT / "scripts" / "gemini_dispatcher.py"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def write_job(payload: Dict[str, Any], name: str) -> Path:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    path = INBOX_DIR / f"job.{name}_{now_stamp()}.json"
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def enqueue_trend_spotter(theme: str) -> Path:
    payload = {
        "id": f"rb-trend-{now_stamp()}",
        "task_type": "trend_spotter",
        "target_profile": "research",
        "inputs": {
            "query": theme,
            "keywords": [x.strip() for x in theme.replace(",", " ").split() if len(x.strip()) >= 3][:8],
        },
        "policy": {"risk": "low", "estimated_spend_usd": 0},
    }
    return write_job(payload, "rb_trend")


def enqueue_draft(concept: str, backend: str) -> Path:
    payload = {
        "id": f"rb-draft-{now_stamp()}",
        "task_type": "product_drafter",
        "target_profile": "research",
        "inputs": {
            "concept": concept,
            "image_backend": backend,
        },
        "policy": {"risk": "low", "estimated_spend_usd": 0},
    }
    return write_job(payload, "rb_draft")


def enqueue_manager() -> Path:
    payload = {
        "id": f"rb-manager-{now_stamp()}",
        "task_type": "manager",
        "target_profile": "research",
        "policy": {"risk": "low", "estimated_spend_usd": 0},
    }
    return write_job(payload, "rb_manager")


def run_dispatcher(env: Dict[str, str]) -> str:
    cp = subprocess.run(
        [sys.executable, str(DISPATCHER)],
        cwd=str(REPO_ROOT),
        text=True,
        capture_output=True,
        env=env,
    )
    output = "\n".join([x for x in [cp.stdout.strip(), cp.stderr.strip()] if x]).strip()
    if output:
        print(output)
    return output


def has_live_receipt(since: dt.datetime) -> bool:
    if not POSTED_DIR.exists():
        return False
    for p in POSTED_DIR.glob("live_*.json"):
        try:
            ts = dt.datetime.fromtimestamp(p.stat().st_mtime)
            if ts >= since:
                return True
        except Exception:
            continue
    return False


def main() -> int:
    ap = argparse.ArgumentParser(description="Run the free-first Redbubble autonomous pipeline.")
    ap.add_argument("--theme", default="minimal geometric symbol art")
    ap.add_argument("--concept", default="")
    ap.add_argument("--image-backend", default="local_lineart", choices=["local_lineart", "sdwebui", "openai"])
    ap.add_argument("--max-cycles", type=int, default=8)
    ap.add_argument("--run-now", action="store_true")
    args = ap.parse_args()

    created: list[Path] = []
    if str(args.concept).strip():
        created.append(enqueue_draft(str(args.concept).strip(), backend=str(args.image_backend).strip().lower()))
    else:
        created.append(enqueue_trend_spotter(str(args.theme).strip()))
    created.append(enqueue_manager())
    print("Queued jobs:")
    for p in created:
        print(f"- {p}")

    if not args.run_now:
        return 0

    env = dict(os.environ)
    env["GEMINI_OP_FREE_MODE"] = "1"
    env["GEMINI_OP_ALLOW_PAID_ART"] = "0"
    env["GEMINI_OP_ART_BACKEND"] = str(args.image_backend).strip().lower()
    started = dt.datetime.now()

    for cycle in range(1, max(1, int(args.max_cycles)) + 1):
        print(f"\n[Cycle {cycle}] dispatch")
        enqueue_manager()
        out = run_dispatcher(env=env)
        if has_live_receipt(started):
            print("Pipeline reached LIVE receipt (mock uploader).")
            return 0
        if "No jobs found." in out:
            break

    print("Pipeline finished cycles. Check:")
    print(f"- drafts: {REPO_ROOT / 'ramshare' / 'evidence' / 'drafts'}")
    print(f"- reviewed: {REPO_ROOT / 'ramshare' / 'evidence' / 'reviewed'}")
    print(f"- staging: {REPO_ROOT / 'ramshare' / 'evidence' / 'staging'}")
    print(f"- posted: {REPO_ROOT / 'ramshare' / 'evidence' / 'posted'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
