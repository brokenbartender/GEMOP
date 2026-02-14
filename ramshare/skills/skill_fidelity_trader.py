import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
EVIDENCE_DIR = REPO_ROOT / "ramshare" / "evidence"
SNAPSHOT_PATH = EVIDENCE_DIR / "portfolio_snapshot.json"
INTENT_LOG_PATH = EVIDENCE_DIR / "trade_intent_log.jsonl"
TRADE_HISTORY_PATH = EVIDENCE_DIR / "trade_history.json"
RECEIPTS_DIR = EVIDENCE_DIR / "trade_receipts"
KILL_SWITCH = REPO_ROOT / "STOP_ALL_AGENTS.flag"
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from evidence_chain import append_signed_entry  # type: ignore  # noqa: E402


def now_iso() -> str:
    return dt.datetime.now().astimezone().isoformat(timespec="seconds")


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def load_json(path: Path, fallback: Dict[str, Any] | None = None) -> Dict[str, Any]:
    if not path.exists():
        return fallback or {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def parse_money(text: str) -> float:
    m = re.search(r"-?\$?\s*([0-9,]+(?:\.[0-9]+)?)", text.replace(",", ""))
    if not m:
        return 0.0
    return float(m.group(1))


def assert_not_killed() -> None:
    if KILL_SWITCH.exists():
        raise SystemExit(f"Kill switch is active: {KILL_SWITCH}")


def append_intent_log(payload: Dict[str, Any]) -> Dict[str, Any]:
    return append_signed_entry(INTENT_LOG_PATH, payload)


def scrape_positions(page) -> List[Dict[str, Any]]:
    selectors = ["table", "table tbody tr", "[data-testid*='position']", "[class*='position']"]
    found = None
    for sel in selectors:
        assert_not_killed()
        try:
            page.wait_for_selector(sel, timeout=8000)
            found = sel
            break
        except PlaywrightTimeoutError:
            continue
    if found is None:
        return []

    rows = page.eval_on_selector_all(
        "table tbody tr",
        """rows => rows.map(r => {
            const cells = Array.from(r.querySelectorAll('td')).map(c => c.innerText.trim());
            return cells;
        })""",
    )
    positions: List[Dict[str, Any]] = []
    for cells in rows:
        if not isinstance(cells, list) or not cells:
            continue
        symbol = str(cells[0]).split()[0].strip().upper()
        quantity = parse_money(cells[2]) if len(cells) > 2 else 0.0
        market_value = parse_money(cells[3]) if len(cells) > 3 else 0.0
        positions.append(
            {
                "symbol": symbol,
                "raw_cells": cells,
                "quantity": quantity,
                "market_value": market_value,
            }
        )
    return positions


def detect_settled_cash(page) -> float:
    txt = page.content()
    m = re.search(r"Settled\s+Cash[^$]{0,40}\$([0-9,]+(?:\.[0-9]{1,2})?)", txt, re.IGNORECASE)
    if not m:
        return 0.0
    return float(m.group(1).replace(",", ""))


def fetch_current_positions() -> Dict[str, Any]:
    profile = os.environ.get("GEMINI_PROFILE", "")
    if profile.lower() not in ("ops", "fidelity"):
        raise SystemExit(f"fidelity_trader requires ops/fidelity profile (current: {profile or 'unset'})")

    login_url = os.environ.get("FIDELITY_LOGIN_URL", "https://digital.fidelity.com/prgw/digital/login/full-page")
    positions_url = os.environ.get(
        "FIDELITY_POSITIONS_URL",
        "https://digital.fidelity.com/ftgw/digital/portfolio/positions",
    )
    headless = os.environ.get("FIDELITY_HEADLESS", "0") == "1"
    wait_after_login_sec = int(os.environ.get("FIDELITY_LOGIN_WAIT_SEC", "60"))

    with sync_playwright() as pw:
        assert_not_killed()
        browser = pw.chromium.launch(headless=headless)
        ctx = browser.new_context()
        page = ctx.new_page()
        assert_not_killed()
        page.goto(login_url, wait_until="domcontentloaded")
        assert_not_killed()
        page.goto(positions_url, wait_until="domcontentloaded")
        page.wait_for_timeout(wait_after_login_sec * 1000)

        assert_not_killed()
        positions = scrape_positions(page)
        settled_cash = detect_settled_cash(page)
        page_html_path = EVIDENCE_DIR / f"fidelity_positions_page_{now_stamp()}.html"
        page_html_path.write_text(page.content(), encoding="utf-8")
        browser.close()

    return {
        "generated_at": now_iso(),
        "positions_count": len(positions),
        "settled_cash": settled_cash,
        "positions": positions,
        "source": "fidelity_playwright",
        "page_capture_path": str(page_html_path),
    }


def record_trade(history_entry: Dict[str, Any]) -> None:
    TRADE_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
    hist = load_json(TRADE_HISTORY_PATH, {"trades": []})
    trades = hist.get("trades") or []
    trades.append(history_entry)
    hist["trades"] = trades[-2000:]
    TRADE_HISTORY_PATH.write_text(json.dumps(hist, indent=2), encoding="utf-8")


def simulate_trade(job_id: str, inputs: Dict[str, Any]) -> Path:
    RECEIPTS_DIR.mkdir(parents=True, exist_ok=True)
    receipt = {
        "job_id": job_id,
        "ts": now_iso(),
        "status": "paper_executed",
        "mode": "paper",
        "symbol": str(inputs.get("symbol") or "").upper(),
        "side": str(inputs.get("action") or "").upper(),
        "quantity": float(inputs.get("quantity") or 0.0),
        "order_type": str(inputs.get("order_type") or "LIMIT").upper(),
        "price": float(inputs.get("estimated_price") or 0.0),
        "notional_usd": float(inputs.get("quantity") or 0.0) * float(inputs.get("estimated_price") or 0.0),
        "pnl": 0.0,
    }
    out = RECEIPTS_DIR / f"paper_trade_{now_stamp()}.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    record_trade(receipt)
    return out


def run_trade(job_id: str, inputs: Dict[str, Any]) -> Path:
    action = str(inputs.get("action") or "").upper()
    if action not in ("BUY", "SELL"):
        raise SystemExit(f"Unsupported action for trade path: {action}")

    # Safety-first: live execution is explicitly locked unless multiple guards are enabled.
    live_requested = bool(inputs.get("live") or False)
    heartbeat_origin = str(job_id).lower().startswith("heartbeat-")
    dual_confirmation_token = str(inputs.get("dual_confirmation_token") or "").strip()
    order_type = str(inputs.get("order_type") or "LIMIT").upper().strip()

    if order_type != "LIMIT":
        raise SystemExit("Blocked: only LIMIT orders are allowed.")

    append_intent_log(
        {
            "job_id": job_id,
            "action": action,
            "symbol": str(inputs.get("symbol") or "").upper(),
            "quantity": float(inputs.get("quantity") or 0.0),
            "estimated_price": float(inputs.get("estimated_price") or 0.0),
            "order_type": order_type,
            "live_requested": live_requested,
            "heartbeat_origin": heartbeat_origin,
        }
    )

    if not live_requested:
        return simulate_trade(job_id, inputs)

    if heartbeat_origin:
        raise SystemExit("Blocked: heartbeat-originated jobs cannot execute live trades.")
    if os.environ.get("FIDELITY_LIVE_ENABLE", "0") != "1":
        raise SystemExit("Blocked: live trading disabled (set FIDELITY_LIVE_ENABLE=1 to unlock).")
    if os.environ.get("FIDELITY_FORCE_LIVE_UNLOCK", "0") != "1":
        raise SystemExit("Blocked: missing force-live unlock (FIDELITY_FORCE_LIVE_UNLOCK=1).")
    if not dual_confirmation_token:
        raise SystemExit("Blocked: dual confirmation token required for live trade.")
    env_token = os.environ.get("FIDELITY_CONFIRM_TOKEN", "").strip()
    if not env_token or dual_confirmation_token != env_token:
        raise SystemExit("Blocked: dual confirmation token mismatch.")

    # Live execution is intentionally disabled until a manual implementation is reviewed.
    raise SystemExit("Blocked: live order placement not implemented. Paper simulation only.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Fidelity trader skill: snapshot + safe paper trading")
    ap.add_argument("job_file", help="Path to job json")
    args = ap.parse_args()
    job = load_json(Path(args.job_file), {})
    job_id = str(job.get("id") or Path(args.job_file).stem)
    inputs = job.get("inputs") or {}
    action = str(inputs.get("action") or "").upper()

    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    assert_not_killed()

    if action in ("BUY", "SELL"):
        receipt_path = run_trade(job_id, inputs)
        print(f"Fidelity paper trade receipt: {receipt_path}")
        return

    snapshot = fetch_current_positions()
    SNAPSHOT_PATH.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"Fidelity snapshot saved: {SNAPSHOT_PATH}")


if __name__ == "__main__":
    main()
