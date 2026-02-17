from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# ```diff fences: the prior pattern incorrectly escaped \s and failed to match.
DIFF_BLOCK_RE = re.compile(r"```diff\s*(.*?)```", flags=re.IGNORECASE | re.DOTALL)

# Sensitive or operational files we never want auto-patched from model output.
BLOCKED_FILES = {
    ".env",
    "gcloud_service_key.json",
    "decision.json",
}
BLOCKED_PREFIXES = (
    ".git/",
    ".agent-jobs/",
)

# Default allowlist: only apply patches to these paths. This reduces risk of
# "diffs" that modify tooling or sensitive areas outside the app surface.
ALLOWED_PREFIXES = (
    "docs/",
    "scripts/",
    "mcp/",
    "configs/",
    "agents/templates/",
)

MAX_PATCH_BYTES = 200_000
MAX_TOUCHED_FILES = 25


def _norm_path(p: str) -> str:
    s = (p or "").strip().replace("\\\\", "/")
    if s.startswith("a/") or s.startswith("b/"):
        s = s[2:]
    return s.lstrip("./")


def extract_diff_blocks(text: str) -> list[str]:
    return [m.group(1) or "" for m in DIFF_BLOCK_RE.finditer(text or "")]


def touched_files_from_patch(patch_text: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for ln in (patch_text or "").splitlines():
        ln = ln.rstrip("\n")
        if ln.startswith("+++ "):
            raw = ln[4:].strip()
            p = _norm_path(raw)
            if p and p not in seen:
                seen.add(p)
                out.append(p)
    return out


def is_blocked(path_rel: str) -> bool:
    p = _norm_path(path_rel)
    if not p:
        return True
    if p in BLOCKED_FILES:
        return True
    for pref in BLOCKED_PREFIXES:
        if p.startswith(pref):
            return True
    return False


def _is_new_file_patch(patch_text: str, path_rel: str) -> bool:
    want = _norm_path(path_rel)
    if not want:
        return False
    low = (patch_text or "").replace("\r\n", "\n")
    if "--- /dev/null" not in low:
        return False
    # Match either "+++ b/<path>" or "+++ <path>"
    return (f"+++ b/{want}" in low) or (f"+++ {want}" in low)


def _salvage_new_file_markdown(patch_text: str, *, repo_root: Path, path_rel: str) -> bool:
    """
    Fallback for LLM-generated "diffs" that are structurally close to unified diff but
    fail `git apply --check` (common failure: missing leading '+'/' ' markers in a new file).

    Safety constraints:
    - only for brand-new files (--- /dev/null)
    - only for docs/*.md
    - only if the target does not already exist
    """
    p = _norm_path(path_rel)
    if not p.startswith("docs/") or not p.endswith(".md"):
        return False
    dst = (repo_root / p).resolve()
    try:
        dst.relative_to(repo_root.resolve())
    except Exception:
        return False
    if dst.exists():
        return False

    lines = (patch_text or "").replace("\r\n", "\n").splitlines()
    content: list[str] = []
    in_hunk = False
    for ln in lines:
        if ln.startswith("@@ "):
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if ln.startswith("--- ") or ln.startswith("+++ ") or ln.startswith("diff --git "):
            break
        if ln.startswith("\\ No newline"):
            continue
        if ln.startswith("+"):
            content.append(ln[1:])
            continue
        if ln.startswith(" "):
            content.append(ln[1:])
            continue
        if ln.startswith("-"):
            continue
        # Salvage: treat unmarked lines as content (LLM forgot diff prefixes).
        content.append(ln)

    if not content:
        return False

    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text("\n".join(content).rstrip("\n") + "\n", encoding="utf-8")
    return True


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_decision(run_dir: Path, round_n: int, agent_id: int) -> dict[str, Any] | None:
    p = run_dir / "state" / "decisions" / f"round{int(round_n)}_agent{int(agent_id)}.json"
    obj = read_json(p)
    return obj if isinstance(obj, dict) else None


def _norm_list(xs: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for x in xs or []:
        p = _norm_path(str(x))
        if p and p not in seen:
            seen.add(p)
            out.append(p)
    return out


def choose_agent_from_supervisor(run_dir: Path, round_n: int) -> int:
    sup = run_dir / "state" / f"supervisor_round{round_n}.json"
    obj = read_json(sup)
    if not isinstance(obj, dict):
        return 0
    verdicts = obj.get("verdicts")
    if not isinstance(verdicts, list):
        return 0
    ok = [v for v in verdicts if isinstance(v, dict) and (v.get("status") == "OK")]
    pool = ok if ok else [v for v in verdicts if isinstance(v, dict)]
    if not pool:
        return 0
    best = sorted(pool, key=lambda v: (int(v.get("score") or 0), -int(v.get("agent") or 0)), reverse=True)[0]
    try:
        return int(best.get("agent") or 0)
    except Exception:
        return 0


def load_agent_output(run_dir: Path, round_n: int, agent_id: int) -> tuple[Path, str]:
    p = run_dir / f"round{round_n}_agent{agent_id}.md"
    if not p.exists():
        p = run_dir / f"agent{agent_id}.md"
    txt = ""
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        txt = ""
    return p, txt


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply ```diff blocks from a council agent output (fail-closed).")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument("--agent", type=int, default=0, help="Agent id (1-based). If omitted, choose best from supervisor.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="Run lightweight verification after apply.")
    ap.add_argument("--require-decision-files", action="store_true", help="Fail if DECISION_JSON files list is missing or does not cover touched files.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = Path(args.run_dir).resolve()
    round_n = max(1, int(args.round))

    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    agent_id = int(args.agent or 0)
    if agent_id <= 0:
        agent_id = choose_agent_from_supervisor(run_dir, round_n)
    if agent_id <= 0:
        (state_dir / f"patch_apply_round{round_n}.json").write_text(
            json.dumps({"ok": False, "reason": "no_agent_selected", "round": round_n}, indent=2),
            encoding="utf-8",
        )
        return 2

    out_path, out_txt = load_agent_output(run_dir, round_n, agent_id)
    decision = load_decision(run_dir, round_n, agent_id)
    decision_files = _norm_list(list((decision or {}).get("files") or []))

    # Reuse supervisor guardrail weakening scan (do not auto-apply shadow code).
    try:
        sys.path.insert(0, str(repo_root / "scripts"))
        from council_supervisor import scan_guardrail_weakening  # type: ignore
    except Exception:
        scan_guardrail_weakening = None

    findings: list[dict[str, Any]] = []
    if scan_guardrail_weakening is not None:
        try:
            findings = list(scan_guardrail_weakening(out_txt) or [])
        except Exception:
            findings = []
    if findings:
        payload = {
            "ok": False,
            "reason": "guardrail_weakening_detected",
            "round": round_n,
            "agent": agent_id,
            "output_path": str(out_path),
            "findings": findings[:25],
        }
        (state_dir / f"patch_apply_round{round_n}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return 3

    diff_blocks = extract_diff_blocks(out_txt)
    # Apply each fenced diff block independently; this makes rollback and reporting safer.
    blocks = [b.strip("\n") for b in diff_blocks if b.strip()]

    report: dict[str, Any] = {
        "ok": True,
        "round": round_n,
        "agent": agent_id,
        "output_path": str(out_path),
        "diff_blocks": len(diff_blocks),
        "blocks": [],
        "dry_run": bool(args.dry_run),
        "ts": time.time(),
    }
    if decision is not None:
        report["decision_path"] = str(run_dir / "state" / "decisions" / f"round{round_n}_agent{agent_id}.json")
        report["decision_files"] = decision_files
    else:
        report["decision_path"] = ""
        report["decision_files"] = []

    if not blocks:
        report["ok"] = True
        report["note"] = "no_diff_blocks_found"
        (state_dir / f"patch_apply_round{round_n}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 0

    # Skip if we already successfully applied this round.
    prior = state_dir / f"patch_apply_round{round_n}.json"
    if prior.exists():
        try:
            obj = read_json(prior)
            if isinstance(obj, dict) and obj.get("ok") is True and obj.get("note") not in ("no_diff_blocks_found",):
                report["note"] = "already_applied"
                (state_dir / f"patch_apply_round{round_n}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
                return 0
        except Exception:
            pass

    allow_any = bool(os.environ.get("GEMINI_OP_PATCH_APPLY_ALLOW_ANY"))

    for bi, block in enumerate(blocks, start=1):
        block_report: dict[str, Any] = {"index": bi, "ok": True}
        if len(block.encode("utf-8", errors="ignore")) > MAX_PATCH_BYTES:
            block_report.update({"ok": False, "reason": "patch_too_large"})
            report["ok"] = False
            report["blocks"].append(block_report)
            continue

        touched = touched_files_from_patch(block)
        touched_norm = _norm_list(touched)
        block_report["touched_files"] = touched_norm

        if args.require_decision_files:
            if decision is None or not decision_files:
                block_report.update({"ok": False, "reason": "missing_decision_files"})
                report["ok"] = False
                report["blocks"].append(block_report)
                continue
            missing = [p for p in touched_norm if p not in set(decision_files)]
            if missing:
                block_report.update({"ok": False, "reason": "touched_files_not_declared_in_decision", "missing": missing[:50]})
                report["ok"] = False
                report["blocks"].append(block_report)
                continue

        if len(touched_norm) > MAX_TOUCHED_FILES:
            block_report.update({"ok": False, "reason": "too_many_files"})
            report["ok"] = False
            report["blocks"].append(block_report)
            continue

        blocked = [p for p in touched_norm if is_blocked(p)]
        if blocked:
            block_report.update({"ok": False, "reason": "blocked_file_touched", "blocked": blocked[:50]})
            report["ok"] = False
            report["blocks"].append(block_report)
            continue

        if not allow_any:
            disallowed = [p for p in touched_norm if not any(_norm_path(p).startswith(pref) for pref in ALLOWED_PREFIXES)]
            if disallowed:
                block_report.update({"ok": False, "reason": "path_not_allowed", "disallowed": disallowed[:50]})
                report["ok"] = False
                report["blocks"].append(block_report)
                continue

        patch_path = state_dir / f"patch_round{round_n}_agent{agent_id}_block{bi}.diff"
        patch_path.write_text(block.strip() + "\n", encoding="utf-8")

        chk = run(["git", "apply", "--check", str(patch_path)], cwd=repo_root)
        block_report["git_apply_check_rc"] = chk.returncode
        if chk.returncode != 0:
            # Salvage path for brand-new docs markdown only.
            try:
                if (
                    len(touched_norm) == 1
                    and _is_new_file_patch(block, touched_norm[0])
                    and _salvage_new_file_markdown(block, repo_root=repo_root, path_rel=touched_norm[0])
                ):
                    block_report["note"] = "salvaged_new_file_markdown"
                    report["blocks"].append(block_report)
                    continue
            except Exception:
                pass
            block_report.update({"ok": False, "reason": "git_apply_check_failed", "stderr": (chk.stderr or "")[-2000:]})
            report["ok"] = False
            report["blocks"].append(block_report)
            continue

        if not args.dry_run:
            aply = run(["git", "apply", "--whitespace=nowarn", str(patch_path)], cwd=repo_root)
            block_report["git_apply_rc"] = aply.returncode
            if aply.returncode != 0:
                block_report.update({"ok": False, "reason": "git_apply_failed", "stderr": (aply.stderr or "")[-2000:]})
                report["ok"] = False
                report["blocks"].append(block_report)
                continue

            if args.verify:
                ver = run([sys.executable, "-m", "compileall", "scripts", "mcp"], cwd=repo_root)
                block_report["verify_rc"] = ver.returncode
                if ver.returncode != 0:
                    # Roll back this block.
                    rb = run(["git", "apply", "-R", str(patch_path)], cwd=repo_root)
                    block_report["rollback_rc"] = rb.returncode
                    block_report.update({"ok": False, "reason": "verification_failed"})
                    report["ok"] = False
                    report["blocks"].append(block_report)
                    continue

        report["blocks"].append(block_report)

    (state_dir / f"patch_apply_round{round_n}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report.get("ok") else 8


if __name__ == "__main__":
    raise SystemExit(main())
