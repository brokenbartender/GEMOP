from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


# ```diff fences: the prior pattern incorrectly escaped \s and failed to match.
DIFF_BLOCK_RE = re.compile(r"```diff\s*(.*?)```", flags=re.IGNORECASE | re.DOTALL)
# ```file <path> fences: for direct full-file writes.
FILE_BLOCK_RE = re.compile(r"```file\s+([^\n]+)\s*\n(.*?)```", flags=re.IGNORECASE | re.DOTALL)

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
    "config/",
    "agents/templates/",
    "work/",
)

MAX_PATCH_BYTES = 200_000
MAX_TOUCHED_FILES = 25


def _norm_path(p: str, target_repo: Path | None = None) -> str:
    s = (p or "").strip().replace("\\\\", "/")
    if s.startswith("a/") or s.startswith("b/"):
        s = s[2:]
    res = s.lstrip("./")
    
    # If target_repo is provided and the path is relative to it, strip the repo name to avoid double-prepending
    if target_repo:
        try:
            # Check if path starts with the repo's name (e.g., work/Enterprise...)
            repo_part = target_repo.name
            if res.startswith(f"work/{repo_part}/"):
                res = res[len(f"work/{repo_part}/"):]
            elif res.startswith(f"{repo_part}/"):
                res = res[len(f"{repo_part}/"):]
        except Exception:
            pass
            
    return res


def extract_file_blocks(text: str) -> list[tuple[str, str]]:
    """Extracts (path, content) from ```file path ... ``` blocks."""
    out = []
    for m in FILE_BLOCK_RE.finditer(text or ""):
        path = m.group(1).strip()
        content = m.group(2)
        out.append((path, content))
    return out


def extract_diff_blocks(text: str) -> list[str]:
    txt = text or ""
    fenced = [m.group(1) or "" for m in DIFF_BLOCK_RE.finditer(txt)]
    if fenced:
        return fenced

    # Fallback: accept raw unified diffs (common when models forget ```diff fences).
    # Heuristic: capture chunks starting at "diff --git" until the next "diff --git" (or EOF).
    lines = txt.replace("\r\n", "\n").splitlines()
    blocks: list[str] = []
    cur: list[str] = []
    in_diff = False
    for ln in lines:
        if ln.startswith("diff --git "):
            if cur:
                blocks.append("\n".join(cur).strip("\n"))
                cur = []
            in_diff = True
        if in_diff:
            cur.append(ln)
    if cur:
        blocks.append("\n".join(cur).strip("\n"))

    # Filter: keep only plausible unified diffs.
    out: list[str] = []
    for b in blocks:
        low = b
        if ("--- " in low and "+++ " in low) and ("@@ " in low or "\n@@ " in low):
            out.append(b)
    return out


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


HUNK_HDR_RE = re.compile(
    r"^@@ -(?P<o_start>\d+)(?:,(?P<o_len>\d+))? \+(?P<n_start>\d+)(?:,(?P<n_len>\d+))? @@"
)


def _count_hunk_lines(hunk_lines: list[str]) -> tuple[int, int]:
    old = 0
    new = 0
    for ln in hunk_lines:
        if ln.startswith("\\ No newline at end of file"):
            continue
        if ln.startswith("+") and not ln.startswith("+++"):
            new += 1
            continue
        if ln.startswith("-") and not ln.startswith("---"):
            old += 1
            continue
        if ln.startswith(" "):
            old += 1
            new += 1
            continue
        # Unknown marker inside a hunk: treat as context to avoid producing invalid headers.
        old += 1
        new += 1
    return old, new


def fix_unified_diff_hunk_counts(diff_text: str) -> tuple[str, bool]:
    """
    Best-effort repair for unified diffs with incorrect @@ header counts.

    Some LLMs emit diffs where the hunk header says (old_len,new_len) that doesn't
    match the number of hunk lines. `git apply` treats that as a hard format error:
    "corrupt patch at line ...".
    """
    lines = (diff_text or "").replace("\r\n", "\n").splitlines()
    if not lines:
        return diff_text, False

    out: list[str] = []
    changed = False
    i = 0
    while i < len(lines):
        ln = lines[i]
        m = HUNK_HDR_RE.match(ln)
        if not m:
            out.append(ln)
            i += 1
            continue

        o_start = m.group("o_start")
        n_start = m.group("n_start")

        hunk_body: list[str] = []
        j = i + 1
        while j < len(lines) and not HUNK_HDR_RE.match(lines[j]):
            # Defensive multi-file diff break.
            if lines[j].startswith("diff --git "):
                break
            if lines[j].startswith("--- ") and j + 1 < len(lines) and lines[j + 1].startswith("+++ "):
                break
            hunk_body.append(lines[j])
            j += 1

        old_cnt, new_cnt = _count_hunk_lines(hunk_body)
        want = f"@@ -{o_start},{old_cnt} +{n_start},{new_cnt} @@"
        if want != ln:
            changed = True
        out.append(want)
        out.extend(hunk_body)
        i = j

    fixed = "\n".join(out).strip() + "\n"
    return fixed, changed


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


def _guess_git_apply_strip_level(patch_text: str) -> int:
    """
    `git apply` defaults to `-p1`. If a patch uses paths like `scripts/foo.py` (no a/ b/ prefixes),
    `-p1` will strip the first component and incorrectly apply to `foo.py` at repo root.
    Detect whether the patch is "git-style" (a/ b/) and select -p accordingly.
    """
    t = (patch_text or "").replace("\r\n", "\n")
    for ln in t.splitlines():
        if ln.startswith("diff --git a/") or ln.startswith("--- a/") or ln.startswith("+++ b/"):
            return 1
    return 0


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    # Be permissive on decode: Windows default encoding can throw on undefined bytes.
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, encoding="utf-8", errors="replace")


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _has_approval(run_dir: Path, *, action_id: str, kind: str) -> bool:
    p = run_dir / "state" / "approvals.jsonl"
    if not p.exists():
        return False
    aid = str(action_id or "").strip()
    if not aid:
        return False
    k = str(kind or "").strip()
    try:
        for ln in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            ln = (ln or "").strip()
            if not ln:
                continue
            try:
                obj = json.loads(ln)
            except Exception:
                continue
            if not isinstance(obj, dict):
                continue
            if str(obj.get("action_id") or "").strip() != aid:
                continue
            if k and str(obj.get("kind") or "").strip() != k:
                continue
            return True
    except Exception:
        return False
    return False


def _write_approval_request(run_dir: Path, *, round_n: int, action_id: str, kind: str, details: dict) -> None:
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": 1,
        "generated_at": time.time(),
        "round": int(round_n),
        "action_id": str(action_id),
        "kind": str(kind),
        "details": details,
        "how_to_approve": {
            "command": f'python scripts/approve_action.py --run-dir "{run_dir}" --action-id "{action_id}" --kind "{kind}" --actor human --note "approved"',
            "artifact": "state/approvals.jsonl",
        },
    }
    (state_dir / f"approval_request_round{int(round_n)}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    md = []
    md.append("# Approval Required")
    md.append("")
    md.append(f"round: {payload['round']}")
    md.append(f"kind: {payload['kind']}")
    md.append(f"action_id: {payload['action_id']}")
    md.append("")
    md.append("## How To Approve")
    md.append("```")
    md.append(payload["how_to_approve"]["command"])
    md.append("```")
    (state_dir / f"approval_request_round{int(round_n)}.md").write_text("\n".join(md).strip() + "\n", encoding="utf-8")


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


def rank_agents_from_supervisor(run_dir: Path, round_n: int) -> list[int]:
    sup = run_dir / "state" / f"supervisor_round{round_n}.json"
    obj = read_json(sup)
    if not isinstance(obj, dict):
        return []
    verdicts = obj.get("verdicts")
    if not isinstance(verdicts, list):
        return []
    ok = [v for v in verdicts if isinstance(v, dict) and (v.get("status") == "OK")]
    pool = ok if ok else [v for v in verdicts if isinstance(v, dict)]
    if not pool:
        return []
    ranked = sorted(pool, key=lambda v: (int(v.get("score") or 0), -int(v.get("agent") or 0)), reverse=True)
    out: list[int] = []
    for v in ranked:
        try:
            aid = int(v.get("agent") or 0)
        except Exception:
            continue
        if aid > 0 and aid not in out:
            out.append(aid)
    return out


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


def _maybe_use_decision_source_path(
    *, run_dir: Path, out_path: Path, out_txt: str, decision: dict[str, Any] | None
) -> tuple[Path, str]:
    """
    If contract_repair produced a DECISION_JSON extracted from a repair artifact, prefer that artifact
    for patch extraction. This lets repair outputs supply missing ```diff blocks.
    """
    if not isinstance(decision, dict):
        return out_path, out_txt
    src = str(decision.get("source_path") or "").strip()
    if not src:
        return out_path, out_txt
    try:
        p = Path(src).expanduser().resolve()
    except Exception:
        return out_path, out_txt
    try:
        p.relative_to(run_dir.resolve())
    except Exception:
        return out_path, out_txt
    if not p.exists() or not p.is_file():
        return out_path, out_txt
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return out_path, out_txt
    if not extract_diff_blocks(txt):
        return out_path, out_txt
    return p, txt


# ```file <path> fences: for direct full-file writes.
FILE_BLOCK_RE = re.compile(r"```file\s+([^\n]+)\s*\n(.*?)```", flags=re.IGNORECASE | re.DOTALL)

def extract_file_blocks(text: str) -> list[tuple[str, str]]:
    """Extracts (path, content) from ```file path ... ``` blocks."""
    out = []
    for m in FILE_BLOCK_RE.finditer(text or ""):
        path = m.group(1).strip()
        content = m.group(2)
        out.append((path, content))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply ```diff blocks from a council agent output (fail-closed).")
    ap.add_argument("--repo-root", required=True)
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--round", type=int, default=2)
    ap.add_argument("--agent", type=int, default=0, help="Agent id (1-based). If omitted, choose best from supervisor.")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verify", action="store_true", help="Run lightweight verification after apply.")
    ap.add_argument("--require-decision-files", action="store_true", help="Fail if DECISION_JSON files list is missing or does not cover touched files.")
    ap.add_argument(
        "--infer-decision-files",
        action="store_true",
        help="If DECISION_JSON is missing/invalid, infer the allowed file list from touched files (still enforces allowlist/blocked paths).",
    )
    ap.add_argument("--require-diff-blocks", action="store_true", help="Fail if no ```diff blocks are present in the chosen agent output.")
    ap.add_argument("--require-approval", action="store_true", help="Require an explicit approval record before applying patches.")
    ap.add_argument("--approval-kind", default="patch_apply", help="Approval kind label (default: patch_apply).")
    ap.add_argument("--require-grounding", action="store_true", help="Require at least one repo file-path citation in the chosen agent output.")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    run_dir = Path(args.run_dir).resolve()
    round_n = max(1, int(args.round))

    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)

    # Multi-repo support: if GEMINI_OP_TARGET_REPO is set, use it as the base for file ops.
    target_repo_env = os.environ.get("GEMINI_OP_TARGET_REPO", "").strip()
    target_repo = Path(target_repo_env).resolve() if target_repo_env else repo_root
    if target_repo_env:
        print(f"[Multi-Repo] Targeting: {target_repo}")

    requested_agent = int(args.agent or 0)
    agent_id = requested_agent
    if agent_id <= 0:
        agent_id = choose_agent_from_supervisor(run_dir, round_n)
    if agent_id <= 0:
        (state_dir / f"patch_apply_round{round_n}.json").write_text(
            json.dumps({"ok": False, "reason": "no_agent_selected", "round": round_n}, indent=2),
            encoding="utf-8",
        )
        return 2

    # If auto-selected agent didn't include diff blocks, fall back to the next-best agent.
    candidates = [agent_id] if requested_agent > 0 else ([agent_id] + [a for a in rank_agents_from_supervisor(run_dir, round_n) if a != agent_id])
    chosen: tuple[int, Path, str, dict[str, Any] | None] | None = None
    for cand in candidates:
        p, txt = load_agent_output(run_dir, round_n, cand)
        # Cheap prefilter: avoid parsing unless we need to.
        if args.require_diff_blocks:
            if not extract_diff_blocks(txt):
                continue
        chosen = (cand, p, txt, load_decision(run_dir, round_n, cand))
        break

    if chosen is None:
        payload = {
            "ok": False,
            "reason": "no_diff_blocks_found_in_any_candidate",
            "round": round_n,
            "agent": agent_id,
        }
        (state_dir / f"patch_apply_round{round_n}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return 4

    agent_id, out_path, out_txt, decision = chosen
    out_path, out_txt = _maybe_use_decision_source_path(run_dir=run_dir, out_path=out_path, out_txt=out_txt, decision=decision)
    decision_files = _norm_list(list((decision or {}).get("files") or []))
    validation_ok = bool((decision or {}).get("validation_ok", True))

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

    file_blocks = extract_file_blocks(out_txt)
    diff_blocks = extract_diff_blocks(out_txt)
    # Apply each fenced diff block independently; this makes rollback and reporting safer.
    blocks = [b.strip("\n") for b in diff_blocks if b.strip()]

    patch_blob = "\n\n".join([b.strip() for b in blocks if (b or "").strip()])
    file_blob = "\n".join([f"{p}:{len(c)}" for p, c in file_blocks])
    action_id = hashlib.sha256(
        ("\n".join([str(repo_root), str(run_dir), str(round_n), str(agent_id), patch_blob, file_blob])).encode("utf-8", errors="ignore")
    ).hexdigest()

    if args.require_grounding:
        cited = set(re.findall(r"(?im)\b(?:docs|scripts|mcp|configs|agents)/[a-z0-9_./\\-]+\b", out_txt or ""))
        cited_ok = False
        for c in cited:
            p = _norm_path(c, target_repo=target_repo)
            if not p:
                continue
            try:
                (repo_root / p).resolve().relative_to(repo_root.resolve())
            except Exception:
                continue
            if (repo_root / p).exists():
                cited_ok = True
                break
        if not cited_ok:
            payload = {
                "ok": False,
                "reason": "grounding_required_missing_citations",
                "round": round_n,
                "agent": agent_id,
                "output_path": str(out_path),
                "action_id": action_id,
            }
            (state_dir / f"patch_apply_round{round_n}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return 5

    if args.require_approval and not _has_approval(run_dir, action_id=action_id, kind=str(args.approval_kind)):
        _write_approval_request(
            run_dir,
            round_n=round_n,
            action_id=action_id,
            kind=str(args.approval_kind),
            details={"agent": agent_id, "output_path": str(out_path)},
        )
        payload = {
            "ok": False,
            "reason": "approval_required",
            "round": round_n,
            "agent": agent_id,
            "output_path": str(out_path),
            "action_id": action_id,
            "approval_kind": str(args.approval_kind),
        }
        (state_dir / f"patch_apply_round{round_n}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return 4

    # Stronger idempotency than "round already applied": hash the actual patch content.
    try:
        from action_ledger import has_action, append_action  # type: ignore
    except Exception:
        has_action = None
        append_action = None

    if has_action is not None and has_action(run_dir, action_id=action_id, kind="patch_apply"):
        payload = {
            "ok": True,
            "skipped": True,
            "reason": "idempotent_skip_already_applied",
            "round": round_n,
            "agent": agent_id,
            "output_path": str(out_path),
            "action_id": action_id,
        }
        (state_dir / f"patch_apply_round{round_n}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return 0

    report: dict[str, Any] = {
        "ok": True,
        "round": round_n,
        "agent": agent_id,
        "output_path": str(out_path),
        "action_id": action_id,
        "diff_blocks": len(diff_blocks),
        "blocks": [],
        "dry_run": bool(args.dry_run),
        "ts": time.time(),
    }
    decision_inferred = False
    if decision is not None:
        report["decision_path"] = str(run_dir / "state" / "decisions" / f"round{round_n}_agent{agent_id}.json")
        report["decision_files"] = decision_files
        report["decision_validation_ok"] = validation_ok
    else:
        report["decision_path"] = ""
        report["decision_files"] = []
        report["decision_validation_ok"] = False

    if not blocks:
        report["ok"] = not bool(args.require_diff_blocks)
        report["note"] = "no_diff_blocks_found"
        if args.require_diff_blocks:
            report["reason"] = "require_diff_blocks_enabled"
        (state_dir / f"patch_apply_round{round_n}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return 4 if args.require_diff_blocks else 0

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

    # Apply direct file blocks first
    for rel_path, content in file_blocks:
        safe_path = _norm_path(rel_path, target_repo=target_repo)
        block_report: dict[str, Any] = {"type": "file", "path": safe_path, "ok": True, "touched_files": [safe_path]}
        
        if is_blocked(safe_path):
            block_report.update({"ok": False, "reason": "blocked_file"})
            report["ok"] = False
            report["blocks"].append(block_report)
            continue

        if not allow_any and not any(safe_path.startswith(pref) for pref in ALLOWED_PREFIXES):
            block_report.update({"ok": False, "reason": "path_not_allowed"})
            report["ok"] = False
            report["blocks"].append(block_report)
            continue

        try:
            dst = target_repo / safe_path
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.write_text(content, encoding="utf-8")
        except Exception as e:
            block_report.update({"ok": False, "reason": f"write_failed: {e}"})
            report["ok"] = False
        
        report["blocks"].append(block_report)

    for bi, block in enumerate(blocks, start=1):
        block_report: dict[str, Any] = {"index": bi, "ok": True}
        if len(block.encode("utf-8", errors="ignore")) > MAX_PATCH_BYTES:
            block_report.update({"ok": False, "reason": "patch_too_large"})
            report["ok"] = False
            report["blocks"].append(block_report)
            continue

        strip_level = _guess_git_apply_strip_level(block)
        block_report["git_apply_strip_level"] = int(strip_level)

        touched = touched_files_from_patch(block)
        touched_norm = _norm_list(touched)
        block_report["touched_files"] = touched_norm

        if args.require_decision_files:
            if decision is None or not decision_files:
                if args.infer_decision_files:
                    decision_inferred = True
                    decision_files = sorted(set(decision_files) | set(touched_norm))
                    report["decision_files"] = decision_files
                    report["decision_validation_ok"] = False
                    block_report["note"] = "decision_files_inferred_from_touched"
                else:
                    block_report.update({"ok": False, "reason": "missing_decision_files"})
                    report["ok"] = False
                    report["blocks"].append(block_report)
                    continue
            missing = [p for p in touched_norm if p not in set(decision_files)]
            if missing:
                if args.infer_decision_files:
                    decision_inferred = True
                    decision_files = sorted(set(decision_files) | set(missing))
                    report["decision_files"] = decision_files
                    report["decision_validation_ok"] = False
                    block_report["note"] = "decision_files_extended_from_touched"
                else:
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
            disallowed = [p for p in touched_norm if not any(_norm_path(p, target_repo=target_repo).startswith(pref) for pref in ALLOWED_PREFIXES)]
            if disallowed:
                block_report.update({"ok": False, "reason": "path_not_allowed", "disallowed": disallowed[:50]})
                report["ok"] = False
                report["blocks"].append(block_report)
                continue

        fixed_block, hdr_fixed = fix_unified_diff_hunk_counts(block.strip())
        if hdr_fixed:
            prev = str(block_report.get("note") or "")
            block_report["note"] = (prev + "|fixed_hunk_counts").strip("|")

        patch_path = state_dir / f"patch_round{round_n}_agent{agent_id}_block{bi}.diff"
        # Avoid CRLF patch artifacts on Windows; `git apply` is happiest with LF.
        patch_path.write_bytes(fixed_block.encode("utf-8", errors="ignore"))

        # Common: agents emit `/dev/null -> path` patches even when the file already exists
        # (for example, when a previous run already created it). Treat as a no-op instead
        # of failing the whole block.
        try:
            if len(touched_norm) == 1 and _is_new_file_patch(block, touched_norm[0]):
                existing = target_repo / touched_norm[0]
                if existing.exists():
                    block_report["note"] = "new_file_already_exists_skip"
                    report["blocks"].append(block_report)
                    continue
        except Exception:
            pass

        chk = run(["git", "apply", f"-p{int(strip_level)}", "--check", str(patch_path)], cwd=target_repo)
        block_report["git_apply_check_rc"] = chk.returncode
        if chk.returncode != 0:
            # Salvage path for brand-new docs markdown only.
            try:
                if (
                    len(touched_norm) == 1
                    and _is_new_file_patch(block, touched_norm[0])
                    and _salvage_new_file_markdown(block, repo_root=target_repo, path_rel=touched_norm[0])
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
            aply = run(["git", "apply", f"-p{int(strip_level)}", "--whitespace=nowarn", str(patch_path)], cwd=target_repo)
            block_report["git_apply_rc"] = aply.returncode
            if aply.returncode != 0:
                block_report.update({"ok": False, "reason": "git_apply_failed", "stderr": (aply.stderr or "")[-2000:]})
                report["ok"] = False
                report["blocks"].append(block_report)
                continue

            if args.verify:
                # Use the repo's verify pipeline when available.
                vp = target_repo / "scripts" / "verify_pipeline.py"
                if vp.exists():
                    ver = run([sys.executable, str(vp), "--repo-root", str(target_repo), "--strict"], cwd=target_repo)
                else:
                    ver = run([sys.executable, "-m", "compileall", "scripts", "mcp"], cwd=target_repo)
                block_report["verify_rc"] = ver.returncode
                if ver.returncode != 0:
                    # Roll back this block.
                    rb = run(["git", "apply", f"-p{int(strip_level)}", "-R", str(patch_path)], cwd=target_repo)
                    block_report["rollback_rc"] = rb.returncode
                    block_report.update({"ok": False, "reason": "verification_failed"})
                    report["ok"] = False
                    report["blocks"].append(block_report)
                    continue

        report["blocks"].append(block_report)

    report["decision_inferred"] = bool(decision_inferred)
    (state_dir / f"patch_apply_round{round_n}.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report.get("ok") and (append_action is not None) and (not bool(args.dry_run)):
        try:
            append_action(
                run_dir,
                action_id=action_id,
                kind="patch_apply",
                details={"round": round_n, "agent": agent_id, "output_path": str(out_path)},
            )
        except Exception:
            pass
    return 0 if report.get("ok") else 8


if __name__ == "__main__":
    raise SystemExit(main())
