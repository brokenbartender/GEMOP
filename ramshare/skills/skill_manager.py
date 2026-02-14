import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional


REPO_ROOT = Path(os.environ.get("GEMINI_OP_REPO_ROOT", Path(__file__).resolve().parent.parent))
INBOX_DIR = REPO_ROOT / "ramshare" / "evidence" / "inbox"
PROCESSED_DIR = REPO_ROOT / "ramshare" / "evidence" / "processed"
AUDIT_LOG = REPO_ROOT / "ramshare" / "evidence" / "audit_log.md"
REVIEWED_DIR = REPO_ROOT / "ramshare" / "evidence" / "reviewed"
STAGING_DIR = REPO_ROOT / "ramshare" / "evidence" / "staging"
POSTED_DIR = REPO_ROOT / "ramshare" / "evidence" / "posted"
PORTFOLIO_PATH = REPO_ROOT / "ramshare" / "evidence" / "portfolio_snapshot.json"
STRATEGY_PATH = REPO_ROOT / "ramshare" / "strategy" / "market_context.json"
REPORTS_DIR = REPO_ROOT / "ramshare" / "evidence" / "reports"

sys.path.insert(0, str(REPO_ROOT / "ramshare" / "skills"))
from skill_librarian import check_and_record_trend  # type: ignore  # noqa: E402


def now_stamp() -> str:
    return dt.datetime.now().strftime("%Y%m%d_%H%M%S")


def append_audit(line: str) -> None:
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    if not AUDIT_LOG.exists():
        AUDIT_LOG.write_text("# Audit Log (Local)\n\n", encoding="utf-8")
    with AUDIT_LOG.open("a", encoding="utf-8") as f:
        f.write(f"- {dt.datetime.now().astimezone().isoformat(timespec='seconds')} [MANAGER] {line}\n")


def extract_first_trend(report_path: Path) -> Optional[str]:
    txt = report_path.read_text(encoding="utf-8", errors="ignore")
    for raw in txt.splitlines():
        line = raw.strip()
        if line.startswith("- "):
            item = line[2:].strip()
            # Skip obvious metadata bullets
            low = item.lower()
            if low.startswith("job_id:") or low.startswith("generated_at:"):
                continue
            if item:
                return item
    return None


def load_json(path: Path) -> Dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def today_local() -> str:
    return dt.datetime.now().astimezone().date().isoformat()


def inbox_has_task(task_type: str, max_age_hours: int = 24) -> bool:
    cutoff = dt.datetime.now().astimezone() - dt.timedelta(hours=max_age_hours)
    for p in INBOX_DIR.glob("*.json"):
        try:
            mtime = dt.datetime.fromtimestamp(p.stat().st_mtime).astimezone()
            if mtime < cutoff:
                continue
        except Exception:
            pass
        try:
            data = load_json(p)
        except Exception:
            continue
        if str(data.get("task_type") or data.get("type") or "").strip() == task_type:
            return True
    return False


def market_context_is_fresh_today() -> bool:
    if not STRATEGY_PATH.exists():
        return False
    try:
        data = load_json(STRATEGY_PATH)
    except Exception:
        return False
    ts = str(data.get("generated_at") or "")
    if not ts:
        return False
    try:
        when = dt.datetime.fromisoformat(ts).astimezone()
    except Exception:
        return False
    return when.date().isoformat() == today_local()


def first_portfolio_symbol() -> str:
    if not PORTFOLIO_PATH.exists():
        return "SPY"
    try:
        snap = load_json(PORTFOLIO_PATH)
    except Exception:
        return "SPY"
    for pos in snap.get("positions") or []:
        sym = str(pos.get("symbol") or "").upper().strip()
        if sym:
            return sym
    return "SPY"


def has_today_market_analysis_for(symbol: str) -> bool:
    if not REPORTS_DIR.exists():
        return False
    prefix = f"market_analysis_{symbol.upper()}_"
    today = today_local()
    for p in REPORTS_DIR.glob(f"{prefix}*.json"):
        try:
            data = load_json(p)
            ts = str(data.get("generated_at") or "")
            if ts and dt.datetime.fromisoformat(ts).astimezone().date().isoformat() == today:
                return True
        except Exception:
            continue
    return False


def has_today_alpha_report() -> bool:
    if not REPORTS_DIR.exists():
        return False
    today = today_local()
    for p in REPORTS_DIR.glob("alpha_report_*.json"):
        try:
            data = load_json(p)
            ts = str(data.get("generated_at") or "")
            if ts and dt.datetime.fromisoformat(ts).astimezone().date().isoformat() == today:
                return True
        except Exception:
            continue
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description="Manager skill: promote trend report into product_drafter job")
    ap.add_argument("job_file", help="Path to manager job json (currently not used deeply; reserved for config)")
    args = ap.parse_args()
    _ = args.job_file

    INBOX_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    promoted_any = False

    # Phase 15 orchestration: schedule strategist first, then analyst.
    if not market_context_is_fresh_today() and not inbox_has_task("market_strategist"):
        job = {
            "id": f"auto-market-strategist-{now_stamp()}",
            "task_type": "market_strategist",
            "target_profile": "research",
            "policy": {"risk": "low", "estimated_spend_usd": 0},
        }
        out = INBOX_DIR / f"job.auto_market_strategist_{now_stamp()}.json"
        out.write_text(json.dumps(job, indent=2), encoding="utf-8")
        append_audit("Scheduled Market Strategist job for daily market context refresh")
        print(f"Manager scheduled market strategist job: {out}")
        promoted_any = True

    elif market_context_is_fresh_today() and not inbox_has_task("market_analyst"):
        ticker = first_portfolio_symbol()
        if not has_today_market_analysis_for(ticker):
            job = {
                "id": f"auto-market-analyst-{ticker}-{now_stamp()}",
                "task_type": "market_analyst",
                "target_profile": "research",
                "inputs": {"ticker": ticker},
                "policy": {"risk": "low", "estimated_spend_usd": 0},
            }
            out = INBOX_DIR / f"job.auto_market_analyst_{ticker}_{now_stamp()}.json"
            out.write_text(json.dumps(job, indent=2), encoding="utf-8")
            append_audit(f"Scheduled Market Analyst job for {ticker} after context refresh")
            print(f"Manager scheduled market analyst job: {out}")
            promoted_any = True

    # Phase 17 orchestration: daily alpha report after context/analyst cycle.
    if not has_today_alpha_report() and not inbox_has_task("alpha_report"):
        hour = dt.datetime.now().astimezone().hour
        if hour >= 16:  # run after market close by default
            job = {
                "id": f"auto-alpha-report-{now_stamp()}",
                "task_type": "alpha_report",
                "target_profile": "research",
                "policy": {"risk": "low", "estimated_spend_usd": 0},
            }
            out = INBOX_DIR / f"job.auto_alpha_report_{now_stamp()}.json"
            out.write_text(json.dumps(job, indent=2), encoding="utf-8")
            append_audit("Scheduled Alpha Report job for daily performance analytics")
            print(f"Manager scheduled alpha report job: {out}")
            promoted_any = True

    reports = sorted(INBOX_DIR.glob("report_trends_*.md"))

    if reports:
        report = reports[0]
        trend = extract_first_trend(report) or "Retro Sci-Fi"
        duplicate, decision = check_and_record_trend(trend, window_days=30)

        moved = PROCESSED_DIR / report.name
        if moved.exists():
            moved = PROCESSED_DIR / f"{report.stem}.{now_stamp()}{report.suffix}"
        shutil.move(str(report), str(moved))

        if duplicate:
            append_audit(f"Skipped duplicate trend '{trend}' (within {decision.get('window_days', 30)} days)")
            print(f"Manager skipped duplicate trend: {trend}")
        else:
            job = {
                "id": f"auto-draft-{now_stamp()}",
                "task_type": "product_drafter",
                "target_profile": "research",
                "input_data": trend,
                "policy": {"risk": "low", "estimated_spend_usd": 0},
            }
            out = INBOX_DIR / f"job.auto_draft_{now_stamp()}.json"
            out.write_text(json.dumps(job, indent=2), encoding="utf-8")
            append_audit(f"Promoted trend '{trend}' to Draft Job")
            print(f"Manager promoted trend to draft job: {out}")
            promoted_any = True

    drafts_dir = REPO_ROOT / "ramshare" / "evidence" / "drafts"
    drafts = sorted(drafts_dir.glob("draft_*.json")) if drafts_dir.exists() else []
    if drafts:
        draft = drafts[0]
        draft_data = load_json(draft)
        title = str(draft_data.get("title") or draft.stem)
        moved = PROCESSED_DIR / draft.name
        if moved.exists():
            moved = PROCESSED_DIR / f"{draft.stem}.{now_stamp()}{draft.suffix}"
        shutil.move(str(draft), str(moved))

        review_job = {
            "id": f"auto-art-review-{now_stamp()}",
            "task_type": "art_director",
            "target_profile": "research",
            "inputs": {"draft_path": str(moved)},
            "policy": {"risk": "low", "estimated_spend_usd": 0},
        }
        out = INBOX_DIR / f"job.auto_art_review_{now_stamp()}.json"
        out.write_text(json.dumps(review_job, indent=2), encoding="utf-8")

        append_audit(f"Promoted Draft '{title}' to Art Director Review Job")
        print(f"Manager promoted draft to art director job: {out}")
        promoted_any = True

    reviewed = sorted(REVIEWED_DIR.glob("reviewed_*.json")) if REVIEWED_DIR.exists() else []
    if reviewed:
        reviewed_item = reviewed[0]
        reviewed_data = load_json(reviewed_item)
        title = str(reviewed_data.get("title") or reviewed_item.stem)
        moved = PROCESSED_DIR / reviewed_item.name
        if moved.exists():
            moved = PROCESSED_DIR / f"{reviewed_item.stem}.{now_stamp()}{reviewed_item.suffix}"
        shutil.move(str(reviewed_item), str(moved))

        listing_job = {
            "id": f"auto-listing-{now_stamp()}",
            "task_type": "listing_generator",
            "target_profile": "research",
            "inputs": {"draft_path": str(moved)},
            "policy": {"risk": "low", "estimated_spend_usd": 0},
        }
        out = INBOX_DIR / f"job.auto_listing_{now_stamp()}.json"
        out.write_text(json.dumps(listing_job, indent=2), encoding="utf-8")

        append_audit(f"Promoted Reviewed Draft '{title}' to Listing Job")
        print(f"Manager promoted reviewed draft to listing job: {out}")
        promoted_any = True

    listings = sorted(STAGING_DIR.glob("listing_*.json")) if STAGING_DIR.exists() else []
    if listings:
        listing = listings[0]
        moved = PROCESSED_DIR / listing.name
        if moved.exists():
            moved = PROCESSED_DIR / f"{listing.stem}.{now_stamp()}{listing.suffix}"
        shutil.move(str(listing), str(moved))

        upload_job = {
            "id": f"auto-upload-{now_stamp()}",
            "task_type": "uploader",
            "target_profile": "ops",
            "inputs": {"listing_path": str(moved)},
            "policy": {"risk": "medium", "estimated_spend_usd": 0},
        }
        out = INBOX_DIR / f"job.auto_upload_{now_stamp()}.json"
        out.write_text(json.dumps(upload_job, indent=2), encoding="utf-8")

        append_audit("Promoted Staged Listing to Upload Job (Profile: OPS)")
        print(f"Manager promoted staged listing to upload job: {out}")
        promoted_any = True

    live_receipts = sorted(POSTED_DIR.glob("live_*.json")) if POSTED_DIR.exists() else []
    if live_receipts:
        live = live_receipts[0]
        moved = PROCESSED_DIR / live.name
        if moved.exists():
            moved = PROCESSED_DIR / f"{live.stem}.{now_stamp()}{live.suffix}"
        shutil.move(str(live), str(moved))

        strategist_job = {
            "id": f"auto-strategist-{now_stamp()}",
            "task_type": "strategist",
            "target_profile": "research",
            "inputs": {"live_receipt_path": str(moved)},
            "policy": {"risk": "low", "estimated_spend_usd": 0},
        }
        out = INBOX_DIR / f"job.auto_strategist_{now_stamp()}.json"
        out.write_text(json.dumps(strategist_job, indent=2), encoding="utf-8")

        append_audit("Promoted Live Receipt to Strategist Job")
        print(f"Manager promoted live receipt to strategist job: {out}")
        promoted_any = True

    if not promoted_any:
        print("Manager: no actionable reports, drafts, reviews, staged listings, or live receipts found")


if __name__ == "__main__":
    main()
