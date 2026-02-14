import argparse
import json
from pathlib import Path

from evidence_chain import verify_log


def main() -> None:
    ap = argparse.ArgumentParser(description="Verify signed evidence chain integrity")
    ap.add_argument(
        "--log-path",
        default=r"C:\Gemini\ramshare\evidence\trade_intent_log.jsonl",
        help="Path to evidence log file",
    )
    args = ap.parse_args()
    res = verify_log(Path(args.log_path))
    print(json.dumps(res, indent=2))
    if not res.get("ok"):
        raise SystemExit(2)


if __name__ == "__main__":
    main()
