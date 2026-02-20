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
DISPATCHER = REPO_ROOT / "scripts" / "gemini_dispatcher.py"
SKILL = REPO_ROOT / "ramshare" / "skills" / "skill_art_syndicate.py"
STYLE_CYCLE = REPO_ROOT / "scripts" / "rb_style_cycle.py"


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def write_job(payload: Dict[str, Any]) -> Path:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    p = INBOX_DIR / f"job.art_syndicate_{now_stamp()}.json"
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return p


def run_dispatcher(env: Dict[str, str]) -> int:
    cp = subprocess.run([sys.executable, str(DISPATCHER)], cwd=str(REPO_ROOT), text=True, capture_output=True, env=env)
    out = "\n".join([x for x in [cp.stdout.strip(), cp.stderr.strip()] if x]).strip()
    if out:
        print(out)
    return cp.returncode


def run_direct(payload: Dict[str, Any]) -> int:
    import tempfile

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as tf:
        tf.write(json.dumps(payload, indent=2))
        job_path = Path(tf.name)
    try:
        cp = subprocess.run([sys.executable, str(SKILL), str(job_path)], cwd=str(REPO_ROOT), text=True, capture_output=True)
        out = "\n".join([x for x in [cp.stdout.strip(), cp.stderr.strip()] if x]).strip()
        if out:
            print(out)
        return cp.returncode
    finally:
        try:
            job_path.unlink(missing_ok=True)
        except Exception:
            pass


def run_style_cycle(*, cycles: int, zip_path: str, dataset_dir: str, themes: str, apply: bool) -> int:
    cmd = [sys.executable, str(STYLE_CYCLE), "--cycles", str(max(1, int(cycles)))]
    if str(zip_path).strip():
        cmd.extend(["--zip", str(zip_path).strip()])
    if str(dataset_dir).strip():
        cmd.extend(["--dataset-dir", str(dataset_dir).strip()])
    if str(themes).strip():
        cmd.extend(["--themes", str(themes).strip()])
    if apply:
        cmd.append("--apply")
    cp = subprocess.run(cmd, cwd=str(REPO_ROOT), text=True, capture_output=True)
    out = "\n".join([x for x in [cp.stdout.strip(), cp.stderr.strip()] if x]).strip()
    if out:
        print(out)
    return cp.returncode


def main() -> int:
    ap = argparse.ArgumentParser(description="Run Art Syndicate council loop for Redbubble concept generation.")
    ap.add_argument("--query", default="trendy spots in michigan 2026")
    ap.add_argument("--max-revisions", type=int, default=4)
    ap.add_argument("--max-candidates", type=int, default=6)
    ap.add_argument("--shop-url", default="")
    ap.add_argument("--no-packet", action="store_true")
    ap.add_argument("--queue", action="store_true", help="Queue job to inbox and run dispatcher.")
    ap.add_argument("--style-cycles", type=int, default=0, help="Run style calibration cycles before council run.")
    ap.add_argument("--style-zip", default="", help="Optional ZIP of reference artwork for style cycles.")
    ap.add_argument("--style-dataset-dir", default="", help="Optional artwork folder for style cycles.")
    ap.add_argument("--style-themes", default="", help="Optional comma-separated variety prompts for style cycles.")
    args = ap.parse_args()

    if int(args.style_cycles) > 0:
        rc_style = run_style_cycle(
            cycles=int(args.style_cycles),
            zip_path=str(args.style_zip),
            dataset_dir=str(args.style_dataset_dir),
            themes=str(args.style_themes),
            apply=True,
        )
        if rc_style != 0:
            return rc_style

    payload = {
        "id": f"art-syndicate-{now_stamp()}",
        "task_type": "art_syndicate",
        "target_profile": "research",
        "inputs": {
            "query": str(args.query).strip(),
            "max_revisions": int(args.max_revisions),
            "max_candidates": int(args.max_candidates),
            "build_upload_packet": not bool(args.no_packet),
            "shop_url": str(args.shop_url).strip(),
        },
        "policy": {"risk": "low", "estimated_spend_usd": 0},
    }
    if not args.queue:
        return run_direct(payload)

    job = write_job(payload)
    print(f"Queued: {job}")
    env = dict(os.environ)
    env["GEMINI_PROFILE"] = "research"
    return run_dispatcher(env=env)


if __name__ == "__main__":
    raise SystemExit(main())
