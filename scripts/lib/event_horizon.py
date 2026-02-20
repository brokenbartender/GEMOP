from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import time
from pathlib import Path


KEYWORD_WEIGHTS = {
    "architecture": 40.0,
    "security": 50.0,
    "compliance": 45.0,
    "database": 35.0,
    "migrate": 30.0,
    "integration": 30.0,
    "orchestrator": 35.0,
    "thermodynamics": 25.0,
    "lyapunov": 25.0,
    "event_horizon": 30.0,
    "hawking": 25.0,
    "patch": 20.0,
    "tests": 20.0,
}

CONSTRAINT_RE = re.compile(
    r"(?i)\b(must|must not|should|should not|required|requirement|constraint|never|always|exactly|at least|without)\b"
)
FILE_RE = re.compile(r"(?i)\b[\w\-./\\]+\.(py|ps1|md|json|toml|yaml|yml|txt)\b")


def _tokenize(text: str) -> list[str]:
    return re.findall(r"\S+", text or "")


def estimate_mass(prompt: str) -> float:
    tokens = _tokenize(prompt)
    if not tokens:
        return 0.0
    mass = float(len(tokens))
    for tok in tokens:
        norm = tok.lower().strip(".,!?;:\"'()[]{}")
        mass += KEYWORD_WEIGHTS.get(norm, 0.0)
    mass += 12.0 * len(CONSTRAINT_RE.findall(prompt))
    mass += 10.0 * len(FILE_RE.findall(prompt))
    bullet_lines = sum(1 for ln in prompt.splitlines() if re.match(r"^\s*([-*]|\d+\.)\s+", ln))
    mass += 6.0 * float(bullet_lines)
    return round(mass, 3)


def mass_breakdown(prompt: str) -> dict[str, float]:
    tokens = _tokenize(prompt)
    token_mass = float(len(tokens))
    keyword_mass = 0.0
    for tok in tokens:
        norm = tok.lower().strip(".,!?;:\"'()[]{}")
        keyword_mass += float(KEYWORD_WEIGHTS.get(norm, 0.0))
    constraint_mass = float(12.0 * len(CONSTRAINT_RE.findall(prompt)))
    file_ref_mass = float(10.0 * len(FILE_RE.findall(prompt)))
    bullet_lines = sum(1 for ln in prompt.splitlines() if re.match(r"^\s*([-*]|\d+\.)\s+", ln))
    structure_mass = float(6.0 * bullet_lines)
    total = round(token_mass + keyword_mass + constraint_mass + file_ref_mass + structure_mass, 3)
    return {
        "token_mass": round(token_mass, 3),
        "keyword_mass": round(keyword_mass, 3),
        "constraint_mass": round(constraint_mass, 3),
        "file_ref_mass": round(file_ref_mass, 3),
        "structure_mass": round(structure_mass, 3),
        "total_mass": total,
    }


def _segment_prompt(prompt: str) -> list[str]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", prompt) if b.strip()]
    if len(blocks) >= 2:
        return blocks
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", prompt) if s.strip()]
    if len(sentences) >= 2:
        return sentences
    return [prompt.strip()] if prompt.strip() else []


def _fallback_chunk(prompt: str, shards: int) -> list[str]:
    toks = _tokenize(prompt)
    if not toks:
        return []
    per = max(1, math.ceil(len(toks) / float(max(1, shards))))
    out = []
    for i in range(0, len(toks), per):
        out.append(" ".join(toks[i : i + per]).strip())
    return [x for x in out if x]


def split_prompt(prompt: str, shard_count: int) -> list[str]:
    if shard_count <= 1:
        return [prompt.strip()] if prompt.strip() else []
    segments = _segment_prompt(prompt)
    if len(segments) <= 1:
        return _fallback_chunk(prompt, shard_count)

    target_mass = max(1.0, estimate_mass(prompt) / float(shard_count))
    shards: list[str] = []
    cur: list[str] = []
    cur_mass = 0.0

    for seg in segments:
        seg_mass = estimate_mass(seg)
        if cur and (cur_mass + seg_mass) > target_mass:
            shards.append("\n\n".join(cur).strip())
            cur = [seg]
            cur_mass = seg_mass
        else:
            cur.append(seg)
            cur_mass += seg_mass

    if cur:
        shards.append("\n\n".join(cur).strip())

    shards = [s for s in shards if s]
    if len(shards) <= 1 and shard_count > 1:
        return _fallback_chunk(prompt, shard_count)
    return shards


def _write_state(run_dir: Path, payload: dict) -> None:
    state_dir = run_dir / "state"
    state_dir.mkdir(parents=True, exist_ok=True)
    out = dict(payload)
    out["ts"] = time.time()
    out_path = state_dir / "event_horizon.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")


def main() -> None:
    ap = argparse.ArgumentParser(description="Phase VI event-horizon prompt density guard.")
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--prompt", default="")
    ap.add_argument("--prompt-file", default="")
    ap.add_argument("--context-radius", type=int, default=0)
    ap.add_argument("--gravity-constant", type=float, default=1.0)
    ap.add_argument("--light-speed", type=float, default=8.0)
    ap.add_argument("--radius-divisor", type=float, default=128.0)
    ap.add_argument("--split-policy", choices=["binary_star", "adaptive"], default="binary_star")
    ap.add_argument("--max-shards", type=int, default=8)
    args = ap.parse_args()

    run_dir = Path(args.run_dir).resolve()
    prompt = str(args.prompt or "")
    if args.prompt_file and not prompt:
        try:
            prompt = Path(args.prompt_file).read_text(encoding="utf-8", errors="ignore")
        except Exception:
            prompt = ""

    radius = int(args.context_radius or 0)
    if radius <= 0:
        try:
            radius = int((os.environ.get("GEMINI_OP_CONTEXT_RADIUS") or "").strip())
        except Exception:
            radius = 0
    if radius <= 0:
        radius = 4096

    breakdown = mass_breakdown(prompt)
    mass = float(breakdown["total_mass"])
    gravity_constant = float(args.gravity_constant)
    light_speed = max(0.001, float(args.light_speed))
    radius_divisor = max(1.0, float(args.radius_divisor))
    radius_units = float(radius) / radius_divisor
    schwarzschild_radius = (2.0 * gravity_constant * mass) / (light_speed**2)
    split_required = schwarzschild_radius > radius_units

    if split_required:
        if args.split_policy == "binary_star":
            shard_count = 2
        else:
            shard_count = int(max(2, math.ceil(schwarzschild_radius / max(radius_units, 0.001))))
    else:
        shard_count = 1
    shard_count = min(max(1, shard_count), max(2, int(args.max_shards)))

    shards = split_prompt(prompt, shard_count) if split_required else []
    if split_required and len(shards) < 2:
        shards = _fallback_chunk(prompt, shard_count)
    if split_required and len(shards) < 2:
        split_required = False
        shards = []

    payload = {
        "split_required": bool(split_required),
        "split_policy": args.split_policy,
        "mass": mass,
        "mass_breakdown": breakdown,
        "physics": {
            "equation": "r_s = 2GM/c^2",
            "G": gravity_constant,
            "c": light_speed,
            "r_s": round(schwarzschild_radius, 6),
            "context_radius_units": round(radius_units, 6),
            "context_radius_raw": radius,
            "radius_divisor": radius_divisor,
            "safety_margin": round(radius_units - schwarzschild_radius, 6),
        },
        "estimated_shards": shard_count if split_required else 1,
        "actual_shards": len(shards),
        "shards": shards,
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8", errors="ignore")).hexdigest() if prompt else "",
    }
    _write_state(run_dir, payload)
    print(json.dumps(payload, separators=(",", ":")))


if __name__ == "__main__":
    main()
