from __future__ import annotations

import argparse
from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def read_text_if_exists(p: Path) -> str:
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="ignore").strip()


def assemble(base_path: Path, profile_path: Path, local_path: Path) -> str:
    parts: list[str] = []

    base = read_text_if_exists(base_path)
    if base:
        parts.append("# --- config/config.base.toml ---")
        parts.append(base)

    prof = read_text_if_exists(profile_path)
    if prof:
        parts.append("")
        parts.append(f"# --- {profile_path.as_posix()} ---")
        parts.append(prof)

    local = read_text_if_exists(local_path)
    if local:
        parts.append("")
        parts.append("# --- config/config.local.toml (ignored) ---")
        parts.append(local)

    # Alatyr-Kamen: The Final Immutable Layer
    alatyr_path = Path(__file__).resolve().parents[1] / "configs" / "alatyr_config.toml"
    alatyr = read_text_if_exists(alatyr_path)
    if alatyr:
        parts.append("")
        parts.append("# --- config/alatyr_config.toml (IMMUTABLE) ---")
        parts.append(alatyr)

    return ("\n".join(parts).strip() + "\n") if parts else ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Assemble an active Gemini config by concatenating base+profile+local.")
    ap.add_argument("--repo-root", default="", help="Repo root (defaults to scripts/..)")
    ap.add_argument("--config-profile", default="full", help="Profile name (e.g. base/core/full/max)")
    ap.add_argument("--out", default="", help="Output path (default: config/config.active.toml)")
    args = ap.parse_args()

    root = Path(args.repo_root).expanduser().resolve() if args.repo_root else repo_root()
    configs_dir = root / "config"

    base_path = configs_dir / "config.base.toml"
    profile_path = configs_dir / "profiles" / f"config.{args.config_profile}.toml"
    local_path = configs_dir / "config.local.toml"
    out_path = Path(args.out).expanduser().resolve() if args.out else (configs_dir / "config.active.toml")

    text = assemble(base_path, profile_path, local_path)
    if not text:
        raise SystemExit(f"No config sources found. Expected {base_path} and/or {profile_path}.")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        existing = out_path.read_text(encoding="utf-8", errors="ignore")
        if existing == text:
            print(f"Config up-to-date: {out_path.name}")
            return 0

    out_path.write_text(text, encoding="utf-8")
    print(f"Config assembled: {out_path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

