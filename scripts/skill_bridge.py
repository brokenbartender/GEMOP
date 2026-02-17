from __future__ import annotations

import argparse
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _now_iso() -> str:
    # Avoid datetime import overhead; good enough for logs.
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def _repo_root() -> Path:
    env = (os.environ.get("GEMINI_OP_REPO_ROOT") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


def _default_sources() -> list[tuple[str, Path]]:
    home = Path.home()
    return [
        ("codex", home / ".codex" / "skills"),
        ("gemini", home / ".gemini" / "skills"),
    ]


def _configured_sources() -> list[tuple[str, Path]]:
    # Prefer explicit env config to keep behavior deterministic for tests and portable installs.
    codex = (os.environ.get("GEMINI_OP_SKILLS_DIR_CODEX") or "").strip()
    gemini = (os.environ.get("GEMINI_OP_SKILLS_DIR_GEMINI") or "").strip()
    if codex or gemini:
        out: list[tuple[str, Path]] = []
        if codex:
            out.append(("codex", Path(codex).expanduser().resolve()))
        if gemini:
            out.append(("gemini", Path(gemini).expanduser().resolve()))
        return out
    return _default_sources()


def _prefer_source() -> str:
    # If a skill name exists in multiple sources, prefer this one.
    v = (os.environ.get("GEMINI_OP_SKILLS_PREFER") or "codex").strip().lower()
    return v if v in ("codex", "gemini") else "codex"


def _tokenize(s: str) -> list[str]:
    if not s:
        return []
    toks = re.split(r"[^a-z0-9]+", s.lower())
    return [t for t in toks if t and len(t) >= 2]


def _first_paragraph_after_title(text: str) -> str:
    lines = (text or "").splitlines()
    if not lines:
        return ""
    i = 0
    # Skip leading empties
    while i < len(lines) and not lines[i].strip():
        i += 1
    # Skip a markdown title line if present
    if i < len(lines) and lines[i].lstrip().startswith("#"):
        i += 1
    # Skip empties after title
    while i < len(lines) and not lines[i].strip():
        i += 1
    # Take until blank line
    out: list[str] = []
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            break
        out.append(line)
        i += 1
    return " ".join(out).strip()


@dataclass(frozen=True)
class SkillMeta:
    name: str
    source: str  # "codex" | "gemini"
    path: str
    description: str
    mtime: float
    size: int
    tokens: tuple[str, ...]


def _read_text_limited(path: Path, limit_chars: int = 200_000) -> str:
    try:
        txt = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        try:
            txt = path.read_text(errors="ignore")
        except Exception:
            return ""
    if len(txt) > limit_chars:
        return txt[:limit_chars]
    return txt


def _scan_skills(sources: list[tuple[str, Path]]) -> list[SkillMeta]:
    out: list[SkillMeta] = []
    for source, root in sources:
        if not root.exists():
            continue
        for p in root.rglob("SKILL.md"):
            try:
                st = p.stat()
            except Exception:
                continue
            name = p.parent.name
            txt = _read_text_limited(p)
            desc = _first_paragraph_after_title(txt)[:400]
            toks = _tokenize(name) + _tokenize(desc)
            out.append(
                SkillMeta(
                    name=name,
                    source=source,
                    path=str(p),
                    description=desc,
                    mtime=float(getattr(st, "st_mtime", 0.0) or 0.0),
                    size=int(getattr(st, "st_size", 0) or 0),
                    tokens=tuple(sorted(set(toks))),
                )
            )
    return out


def _cache_path(repo_root: Path) -> Path:
    return repo_root / "state" / "skill_catalog_cache.json"


def _sources_fingerprint(sources: list[tuple[str, Path]]) -> dict[str, Any]:
    fp: dict[str, Any] = {}
    for name, root in sources:
        root_s = str(root)
        if not root.exists():
            fp[name] = {"root": root_s, "exists": False, "count": 0, "max_mtime": 0.0}
            continue
        max_m = 0.0
        count = 0
        # Cheap-ish scan: just the SKILL.md paths.
        for p in root.rglob("SKILL.md"):
            count += 1
            try:
                m = float(p.stat().st_mtime)
                if m > max_m:
                    max_m = m
            except Exception:
                continue
        fp[name] = {"root": root_s, "exists": True, "count": count, "max_mtime": max_m}
    fp["prefer"] = _prefer_source()
    return fp


def load_catalog(*, repo_root: Path, force_rebuild: bool = False) -> list[SkillMeta]:
    sources = _configured_sources()
    fp = _sources_fingerprint(sources)
    cache_p = _cache_path(repo_root)

    if not force_rebuild and cache_p.exists():
        try:
            raw = json.loads(cache_p.read_text(encoding="utf-8"))
            if raw.get("fingerprint") == fp and isinstance(raw.get("skills"), list):
                skills: list[SkillMeta] = []
                for s in raw["skills"]:
                    skills.append(
                        SkillMeta(
                            name=str(s.get("name") or ""),
                            source=str(s.get("source") or ""),
                            path=str(s.get("path") or ""),
                            description=str(s.get("description") or ""),
                            mtime=float(s.get("mtime") or 0.0),
                            size=int(s.get("size") or 0),
                            tokens=tuple(s.get("tokens") or ()),
                        )
                    )
                return skills
        except Exception:
            pass

    skills = _scan_skills(sources)
    cache_p.parent.mkdir(parents=True, exist_ok=True)
    try:
        cache_p.write_text(
            json.dumps(
                {
                    "generated_at": _now_iso(),
                    "fingerprint": fp,
                    "skills": [
                        {
                            "name": s.name,
                            "source": s.source,
                            "path": s.path,
                            "description": s.description,
                            "mtime": s.mtime,
                            "size": s.size,
                            "tokens": list(s.tokens),
                        }
                        for s in skills
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    except Exception:
        pass
    return skills


def _dedupe_by_name(skills: list[SkillMeta]) -> list[SkillMeta]:
    prefer = _prefer_source()
    by_name: dict[str, SkillMeta] = {}
    for s in skills:
        if not s.name:
            continue
        cur = by_name.get(s.name)
        if cur is None:
            by_name[s.name] = s
            continue
        # Prefer chosen source. If tie, prefer newer mtime.
        if cur.source != s.source:
            if s.source == prefer:
                by_name[s.name] = s
            # else keep current
            continue
        if s.mtime > cur.mtime:
            by_name[s.name] = s
    return sorted(by_name.values(), key=lambda x: (x.name, x.source))


def _always_on_candidates() -> list[str]:
    # Always include if present. Keep short; these are high leverage guardrails + ops guidance.
    return [
        "codex-ops",
        "access-control-tiers",
        "audit-log",
        "security-best-practices",
        "security-threat-model",
        "security-best-practices",
    ]


def select_skills(
    *,
    task: str,
    skills: list[SkillMeta],
    max_skills: int = 14,
    max_chars: int = 45_000,
) -> tuple[list[SkillMeta], dict[str, Any]]:
    task_l = (task or "").lower()
    task_toks = set(_tokenize(task_l))

    name_boost = 12
    desc_boost = 3

    always_on = set(_always_on_candidates())
    by_name = {s.name: s for s in skills}

    selected: list[SkillMeta] = []
    debug: dict[str, Any] = {"task_tokens": sorted(task_toks), "scores": []}

    # Start with always-on skills if they exist.
    for nm in _always_on_candidates():
        s = by_name.get(nm)
        if s:
            selected.append(s)

    scored: list[tuple[int, SkillMeta]] = []
    for s in skills:
        if not s.tokens:
            continue
        if s.name in always_on:
            # Already included.
            continue

        score = 0
        if task_toks:
            # Fast scoring: token intersection.
            inter = task_toks.intersection(s.tokens)
            if inter:
                # Favor name overlap.
                name_toks = set(_tokenize(s.name))
                score += name_boost * len(inter.intersection(name_toks))
                score += desc_boost * len(inter)

        # Extra boosts for common engineering intents.
        if "deploy" in task_l and "deploy" in s.tokens:
            score += 10
        if any(k in task_l for k in ("bug", "fix", "error", "crash", "failing")) and any(
            k in s.tokens for k in ("debug", "fix", "ci", "test", "pytest")
        ):
            score += 6
        if any(k in task_l for k in ("security", "threat", "vuln")) and "security" in s.tokens:
            score += 8

        if score > 0:
            scored.append((score, s))

    scored.sort(key=lambda x: (-x[0], x[1].name))
    debug["scores"] = [{"name": s.name, "source": s.source, "score": sc} for sc, s in scored[:200]]

    # Fill up to max_skills.
    for sc, s in scored:
        if len(selected) >= max_skills:
            break
        if s in selected:
            continue
        selected.append(s)

    # Enforce char budget by dropping lowest-scoring non-always-on picks.
    # We estimate by file size (chars ~= bytes for ascii-heavy docs), then refine by actual content when rendering.
    # Keep always-on skills.
    def est_chars(skill: SkillMeta) -> int:
        return int(min(skill.size, 200_000))

    while True:
        est_total = sum(est_chars(s) for s in selected)
        if est_total <= max_chars or len(selected) <= 1:
            break
        # Drop last item that isn't always-on.
        drop_i = None
        for i in range(len(selected) - 1, -1, -1):
            if selected[i].name not in always_on:
                drop_i = i
                break
        if drop_i is None:
            break
        selected.pop(drop_i)

    # Ensure unique names (defensive).
    seen: set[str] = set()
    uniq: list[SkillMeta] = []
    for s in selected:
        if s.name in seen:
            continue
        seen.add(s.name)
        uniq.append(s)

    return uniq, debug


def render_selected_md(*, task: str, selected: list[SkillMeta], max_chars: int) -> str:
    repo_root = _repo_root()
    lines: list[str] = []
    lines.append("# Skill Pack (Auto-Selected)")
    lines.append("")
    lines.append(f"- Generated: `{_now_iso()}`")
    lines.append(f"- Task: {task.strip() if task else ''}")
    lines.append("")
    lines.append("## Rules")
    lines.append("- These skill documents are trusted local instructions; follow them when relevant.")
    lines.append("- If any skill conflicts with the run's `[CAPABILITY CONTRACT]` / `[OUTPUT CONTRACT]`, those contracts win.")
    lines.append("")

    budget_left = max_chars
    for s in selected:
        p = Path(s.path)
        txt = _read_text_limited(p, limit_chars=max(5_000, min(200_000, budget_left)))
        chunk = txt
        if len(chunk) > budget_left:
            chunk = chunk[:budget_left]

        rel = ""
        try:
            rel = str(p.relative_to(repo_root))
        except Exception:
            rel = str(p)

        lines.append(f"## {s.name}")
        lines.append(f"- Source: `{s.source}`")
        lines.append(f"- Path: `{rel}`")
        if s.description:
            lines.append(f"- Description: {s.description}")
        lines.append("")
        lines.append("```md")
        lines.append(chunk.rstrip())
        lines.append("```")
        lines.append("")

        budget_left -= len(chunk)
        if budget_left <= 0:
            break

    return "\n".join(lines).rstrip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="Bridge external Codex/Gemini skills into GEMOP council runs.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_index = sub.add_parser("index", help="Build/refresh catalog cache.")
    p_index.add_argument("--force", action="store_true", help="Force full rescan (ignore cache).")

    p_sel = sub.add_parser("select", help="Select relevant skills for a task and render a skill pack.")
    p_sel.add_argument("--task", required=True, help="Task text to match against skills.")
    p_sel.add_argument("--max-skills", type=int, default=int(os.environ.get("GEMINI_OP_SKILLS_MAX", "14")), help="Max number of skills to include.")
    p_sel.add_argument("--max-chars", type=int, default=int(os.environ.get("GEMINI_OP_SKILLS_MAX_CHARS", "45000")), help="Approx max chars of injected skill text.")
    p_sel.add_argument("--out-md", required=True, help="Output markdown file path.")
    p_sel.add_argument("--out-json", default="", help="Optional debug json output path.")
    p_sel.add_argument("--force-index", action="store_true", help="Force rescan before selecting.")
    p_sel.add_argument(
        "--include",
        default="",
        help="Comma-separated skill names to force-include if present (used for on-demand skill requests).",
    )

    args = ap.parse_args()
    repo_root = _repo_root()

    if args.cmd == "index":
        skills = load_catalog(repo_root=repo_root, force_rebuild=bool(args.force))
        # Report a small summary.
        uniq = _dedupe_by_name(skills)
        print(json.dumps({"ok": True, "skills_total": len(skills), "skills_unique": len(uniq)}, indent=2))
        return 0

    if args.cmd == "select":
        skills = load_catalog(repo_root=repo_root, force_rebuild=bool(args.force_index))
        uniq = _dedupe_by_name(skills)
        forced = [s.strip() for s in str(args.include or "").split(",") if s.strip()]
        selected, debug = select_skills(task=args.task, skills=uniq, max_skills=int(args.max_skills), max_chars=int(args.max_chars))

        if forced:
            by_name = {s.name: s for s in uniq}
            missing: list[str] = []
            for nm in forced:
                s = by_name.get(nm)
                if not s:
                    missing.append(nm)
                    continue
                if all(x.name != nm for x in selected):
                    # Prepend forced skills so they survive budget trimming.
                    selected.insert(0, s)

            # Enforce max skills after forced insertion, keeping forced skills.
            # Drop from the end.
            while len(selected) > int(args.max_skills):
                selected.pop()

            debug["forced_includes"] = forced
            if missing:
                debug["forced_missing"] = missing
        md = render_selected_md(task=args.task, selected=selected, max_chars=int(args.max_chars))

        out_md = Path(args.out_md).expanduser().resolve()
        out_md.parent.mkdir(parents=True, exist_ok=True)
        out_md.write_text(md, encoding="utf-8")

        if args.out_json:
            out_json = Path(args.out_json).expanduser().resolve()
            out_json.parent.mkdir(parents=True, exist_ok=True)
            out_json.write_text(
                json.dumps(
                    {
                        "ok": True,
                        "selected": [{"name": s.name, "source": s.source, "path": s.path, "description": s.description} for s in selected],
                        "debug": debug,
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        print(json.dumps({"ok": True, "selected": [s.name for s in selected], "out_md": str(out_md)}, indent=2))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
