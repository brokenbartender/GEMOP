from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parents[1]))
EVIDENCE_DIR = REPO_ROOT / "ramshare" / "evidence"
INBOX_DIR = EVIDENCE_DIR / "inbox"
SNAPSHOT_PATH = EVIDENCE_DIR / "portfolio_snapshot.json"
PROFILE_SKILL = REPO_ROOT / "ramshare" / "skills" / "skill_fidelity_profile.py"
TRADER_SKILL = REPO_ROOT / "ramshare" / "skills" / "skill_fidelity_trader.py"


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def as_float(v: Any, default: float = 0.0) -> float:
    try:
        if isinstance(v, str):
            s = v.replace(",", "").replace("$", "").strip()
            if not s:
                return default
            return float(s)
        return float(v)
    except Exception:
        return default


def parse_account_value_from_text(blob: str) -> float:
    if not blob:
        return 0.0
    m = re.search(r"account\s+value[^0-9$-]*\$?\s*([0-9][0-9,]*\.?[0-9]*)", blob, re.IGNORECASE)
    if not m:
        return 0.0
    return as_float(m.group(1), 0.0)


def normalize_symbol(s: str) -> str:
    sym = re.sub(r"[^A-Za-z0-9.\-]", "", (s or "").upper())
    if sym in {"CASH", "HELD", "SYMBOL"}:
        return ""
    if len(sym) > 7:
        return ""
    return sym


def normalize_header(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").strip().lower()).strip()


HEADER_ALIASES = {
    "symbol": ("symbol", "ticker", "investment", "security"),
    "quantity": ("quantity", "qty", "shares"),
    "price": ("price", "last price", "share price", "current price", "last"),
    "current_value": ("current value", "market value", "value", "position value"),
    "cost_basis": ("cost basis", "total cost basis", "cost basis total", "cost"),
}


def score_header_row(row: List[str]) -> int:
    row_norm = [normalize_header(c) for c in row]
    score = 0
    for aliases in HEADER_ALIASES.values():
        for c in row_norm:
            if any(a in c for a in aliases):
                score += 1
                break
    return score


def detect_header(rows: List[List[str]]) -> Tuple[int, Dict[str, int]]:
    best_idx = -1
    best_score = -1
    for i, row in enumerate(rows[:40]):
        s = score_header_row(row)
        if s > best_score:
            best_score = s
            best_idx = i
    if best_idx < 0 or best_score < 2:
        return (-1, {})

    header = [normalize_header(c) for c in rows[best_idx]]
    idx_map: Dict[str, int] = {}
    for key, aliases in HEADER_ALIASES.items():
        for i, c in enumerate(header):
            if any(a in c for a in aliases):
                idx_map[key] = i
                break
    return (best_idx, idx_map)


def parse_csv_positions(path: Path) -> Tuple[List[Dict[str, Any]], float]:
    blob = path.read_text(encoding="utf-8-sig", errors="ignore")
    acct_value = parse_account_value_from_text(blob)
    rows = list(csv.reader(blob.splitlines()))
    hdr_idx, idx_map = detect_header(rows)
    out: List[Dict[str, Any]] = []

    if hdr_idx >= 0:
        for row in rows[hdr_idx + 1 :]:
            if not row or all(not str(c).strip() for c in row):
                continue
            sym = ""
            if "symbol" in idx_map and idx_map["symbol"] < len(row):
                sym = normalize_symbol(str(row[idx_map["symbol"]]))
            if not sym and row:
                sym = normalize_symbol(str(row[0]))
            if not sym:
                continue
            qty = as_float(row[idx_map["quantity"]], 0.0) if "quantity" in idx_map and idx_map["quantity"] < len(row) else 0.0
            price = as_float(row[idx_map["price"]], 0.0) if "price" in idx_map and idx_map["price"] < len(row) else 0.0
            value = (
                as_float(row[idx_map["current_value"]], 0.0)
                if "current_value" in idx_map and idx_map["current_value"] < len(row)
                else 0.0
            )
            cost = as_float(row[idx_map["cost_basis"]], 0.0) if "cost_basis" in idx_map and idx_map["cost_basis"] < len(row) else 0.0
            if value <= 0 and qty > 0 and price > 0:
                value = qty * price
            if qty <= 0 and value <= 0:
                continue
            out.append(
                {
                    "symbol": sym,
                    "quantity": round(qty, 6),
                    "price": round(price, 6),
                    "current_value": round(value, 2),
                    "cost_basis": round(cost, 2),
                }
            )

    if not out:
        for line in blob.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^([A-Z]{1,6})\b", line)
            if not m:
                continue
            sym = normalize_symbol(m.group(1))
            if not sym:
                continue
            before_first_price = line.split("$", 1)[0]
            qty_candidates = re.findall(r"-?[0-9][0-9,]*\.?[0-9]*", before_first_price)
            qty = as_float(qty_candidates[-1], 0.0) if qty_candidates else 0.0
            dollars = re.findall(r"\$([0-9][0-9,]*\.?[0-9]*)", line)
            dvals = [as_float(v, 0.0) for v in dollars]
            price = dvals[0] if len(dvals) >= 1 else 0.0
            cost = dvals[1] if len(dvals) >= 2 else 0.0
            value = dvals[2] if len(dvals) >= 3 else (qty * price if qty > 0 and price > 0 else 0.0)
            if qty <= 0 and value <= 0:
                continue
            out.append(
                {
                    "symbol": sym,
                    "quantity": round(qty, 6),
                    "price": round(price, 6),
                    "current_value": round(value, 2),
                    "cost_basis": round(cost, 2),
                }
            )

    return (out, acct_value)


def parse_json_positions(path: Path) -> Tuple[List[Dict[str, Any]], float]:
    raw = json.loads(path.read_text(encoding="utf-8-sig"))
    rows: List[Dict[str, Any]] = []
    acct_value = 0.0
    if isinstance(raw, dict):
        acct_value = as_float(raw.get("account_value"), 0.0)
        if isinstance(raw.get("positions"), list):
            rows = [x for x in raw["positions"] if isinstance(x, dict)]
    elif isinstance(raw, list):
        rows = [x for x in raw if isinstance(x, dict)]

    out: List[Dict[str, Any]] = []
    for row in rows:
        sym = normalize_symbol(str(row.get("symbol") or row.get("ticker") or ""))
        if not sym:
            continue
        qty = as_float(row.get("quantity", row.get("qty", row.get("shares", 0.0))), 0.0)
        price = as_float(row.get("price", row.get("last_price", row.get("current_price", 0.0))), 0.0)
        value = as_float(row.get("current_value", row.get("market_value", row.get("value", 0.0))), 0.0)
        cost = as_float(row.get("cost_basis", row.get("cost", 0.0)), 0.0)
        if value <= 0 and qty > 0 and price > 0:
            value = qty * price
        if qty <= 0 and value <= 0:
            continue
        out.append(
            {
                "symbol": sym,
                "quantity": round(qty, 6),
                "price": round(price, 6),
                "current_value": round(value, 2),
                "cost_basis": round(cost, 2),
            }
        )
    return (out, acct_value)


def write_snapshot(*, positions: List[Dict[str, Any]], account_value: float, source: str) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    settled_cash = max(0.0, round(account_value - sum(as_float(p.get("current_value"), 0.0) for p in positions), 2))
    snapshot = {
        "generated_at": now_iso(),
        "positions_count": len(positions),
        "settled_cash": settled_cash,
        "positions": positions,
        "source": source,
    }
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")


def write_profile_job(
    *,
    account_id: str,
    account_value: float,
    positions: List[Dict[str, Any]],
    search_depth: str,
    min_source_trust_score: int,
    offline: bool,
    source_note: str,
) -> Path:
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    stamp = now_stamp()
    job_path = INBOX_DIR / f"job.fidelity_profile_{stamp}.json"
    job = {
        "id": f"fidelity-profile-{stamp}",
        "task_type": "fidelity_profile",
        "target_profile": "fidelity",
        "inputs": {
            "account_id": account_id,
            "account_value": account_value,
            "positions": positions,
            "search_depth": search_depth,
            "min_source_trust_score": min_source_trust_score,
            "offline": offline,
            "source_note": source_note,
        },
    }
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    return job_path


def run_profile(job_path: Path) -> int:
    if not PROFILE_SKILL.exists():
        print(f"ERROR: missing skill script: {PROFILE_SKILL}")
        return 1
    cp = subprocess.run([sys.executable, str(PROFILE_SKILL), str(job_path)], capture_output=True, text=True)
    if cp.stdout.strip():
        print(cp.stdout.strip())
    if cp.returncode != 0 and cp.stderr.strip():
        print(cp.stderr.strip())
    return cp.returncode


def run_playwright_snapshot() -> int:
    if not TRADER_SKILL.exists():
        print(f"ERROR: missing skill script: {TRADER_SKILL}")
        return 1
    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    job_path = INBOX_DIR / f"job.fidelity_snapshot_{now_stamp()}.json"
    job = {
        "id": f"fidelity-snapshot-{now_stamp()}",
        "task_type": "fidelity_trader",
        "target_profile": "fidelity",
        "inputs": {},
    }
    job_path.write_text(json.dumps(job, indent=2), encoding="utf-8")
    cp = subprocess.run([sys.executable, str(TRADER_SKILL), str(job_path)], capture_output=True, text=True)
    if cp.stdout.strip():
        print(cp.stdout.strip())
    if cp.returncode != 0 and cp.stderr.strip():
        print(cp.stderr.strip())
    return cp.returncode


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Fidelity intake bridge: CSV/manual/aggregator/playwright -> profile job")
    sub = ap.add_subparsers(dest="mode", required=True)

    def add_common(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--account-id", default="unknown")
        sp.add_argument("--account-value", type=float, default=0.0)
        sp.add_argument("--search-depth", default="deep", choices=["standard", "deep"])
        sp.add_argument("--min-source-trust-score", type=int, default=0)
        sp.add_argument("--offline", action="store_true")
        sp.add_argument("--run-profile", action="store_true")

    p_csv = sub.add_parser("csv", help="Ingest Fidelity CSV export")
    p_csv.add_argument("--path", required=True, help="Path to CSV export")
    add_common(p_csv)

    p_raw = sub.add_parser("raw", help="Ingest raw fidelity text (copied table)")
    p_raw.add_argument("--path", required=True, help="Path to text file")
    add_common(p_raw)

    p_json = sub.add_parser("json", help="Ingest normalized aggregator/Fidelity JSON")
    p_json.add_argument("--path", required=True, help="Path to JSON")
    add_common(p_json)

    p_play = sub.add_parser("playwright", help="Snapshot via Playwright adapter (higher maintenance risk)")
    p_play.add_argument("--account-id", default="unknown")
    p_play.add_argument("--search-depth", default="deep", choices=["standard", "deep"])
    p_play.add_argument("--min-source-trust-score", type=int, default=0)
    p_play.add_argument("--offline", action="store_true")
    p_play.add_argument("--run-profile", action="store_true")
    return ap.parse_args()


def main() -> int:
    args = parse_args()

    if args.mode == "playwright":
        rc = run_playwright_snapshot()
        if rc != 0:
            return rc
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8-sig"))
        positions = [x for x in snapshot.get("positions", []) if isinstance(x, dict)]
        account_value = sum(as_float(p.get("market_value", p.get("current_value", 0.0)), 0.0) for p in positions)
        normalized = []
        for p in positions:
            symbol = normalize_symbol(str(p.get("symbol") or ""))
            if not symbol:
                continue
            qty = as_float(p.get("quantity"), 0.0)
            value = as_float(p.get("current_value", p.get("market_value", 0.0)), 0.0)
            price = value / qty if qty > 0 else 0.0
            normalized.append(
                {
                    "symbol": symbol,
                    "quantity": qty,
                    "price": round(price, 6),
                    "current_value": round(value, 2),
                    "cost_basis": 0.0,
                }
            )
        job_path = write_profile_job(
            account_id=args.account_id,
            account_value=account_value,
            positions=normalized,
            search_depth=args.search_depth,
            min_source_trust_score=int(args.min_source_trust_score),
            offline=bool(args.offline),
            source_note="playwright_snapshot",
        )
        print(f"Profile job written: {job_path}")
        if args.run_profile:
            return run_profile(job_path)
        return 0

    src = Path(args.path).resolve()
    if not src.exists():
        print(f"ERROR: file not found: {src}")
        return 1

    if args.mode == "csv":
        positions, parsed_account_value = parse_csv_positions(src)
        source_note = "fidelity_csv"
    elif args.mode == "raw":
        positions, parsed_account_value = parse_csv_positions(src)
        source_note = "fidelity_raw_text"
    else:
        positions, parsed_account_value = parse_json_positions(src)
        source_note = "aggregator_json"

    if not positions:
        print("ERROR: no positions parsed from input.")
        return 2

    account_value = float(args.account_value or 0.0)
    if account_value <= 0:
        account_value = parsed_account_value
    if account_value <= 0:
        account_value = round(sum(as_float(p.get("current_value"), 0.0) for p in positions), 2)

    write_snapshot(positions=positions, account_value=account_value, source=source_note)
    print(f"Snapshot written: {SNAPSHOT_PATH}")

    job_path = write_profile_job(
        account_id=args.account_id,
        account_value=account_value,
        positions=positions,
        search_depth=args.search_depth,
        min_source_trust_score=int(args.min_source_trust_score),
        offline=bool(args.offline),
        source_note=source_note,
    )
    print(f"Profile job written: {job_path}")

    if args.run_profile:
        return run_profile(job_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

