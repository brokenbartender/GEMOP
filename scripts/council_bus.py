from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List


def now_ts() -> float:
    return time.time()


def ensure_bus(run_dir: Path) -> Path:
    bus = run_dir / "bus"
    bus.mkdir(parents=True, exist_ok=True)
    return bus


def messages_path(run_dir: Path) -> Path:
    return ensure_bus(run_dir) / "messages.jsonl"


def state_path(run_dir: Path) -> Path:
    return ensure_bus(run_dir) / "state.json"


def append_jsonl(path: Path, row: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, separators=(",", ":")) + "\n")


def load_messages(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for ln in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def load_state(run_dir: Path) -> Dict[str, Any]:
    p = state_path(run_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def save_state(run_dir: Path, state: Dict[str, Any]) -> None:
    p = state_path(run_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2), encoding="utf-8")


def status_index(rows: List[Dict[str, Any]]) -> Dict[str, str]:
    idx: Dict[str, str] = {}
    t = now_ts()
    for r in rows:
        intent = str(r.get("intent", "")).lower()
        if float(r.get("expires_at", 0)) < t:
            continue
        payload = r.get("payload") or {}
        if not isinstance(payload, dict):
            continue
        mid = str(payload.get("message_id") or "")
        if not mid:
            continue
        if intent == "claim":
            idx[mid] = "claimed"
        elif intent == "ack":
            idx[mid] = "acked"
    return idx


def cmd_init(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    bus = ensure_bus(run_dir)
    msg_file = messages_path(run_dir)
    if not msg_file.exists():
        msg_file.write_text("", encoding="utf-8")
    st = {
        "created_at": now_ts(),
        "pattern": args.pattern,
        "agents": args.agents,
        "max_rounds": args.max_rounds,
        "quorum": max(1, int(args.quorum)),
        "decisions": {},
    }
    save_state(run_dir, st)
    print(json.dumps({"ok": True, "bus": str(bus), "state": st}, indent=2))


def cmd_send(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    if args.payload_file:
        payload = json.loads(Path(args.payload_file).read_text(encoding="utf-8"))
    else:
        payload = {"message": args.message or ""}
    row = {
        "id": str(uuid.uuid4()),
        "ts": now_ts(),
        "from": args.sender,
        "to": args.receiver,
        "intent": args.intent,
        "status": "open",
        "ttl_sec": int(args.ttl_sec),
        "expires_at": now_ts() + int(args.ttl_sec),
        "payload": payload,
        "trace_id": args.trace_id or str(uuid.uuid4()),
    }
    append_jsonl(messages_path(run_dir), row)
    print(json.dumps({"ok": True, "message_id": row["id"], "trace_id": row["trace_id"]}, indent=2))


def cmd_recv(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    rows = load_messages(messages_path(run_dir))
    idx = status_index(rows)
    t = now_ts()
    out = []
    for r in rows:
        if r.get("to") != args.agent:
            continue
        if str(r.get("intent", "")).lower() in {"ack", "claim"}:
            continue
        current_status = idx.get(str(r.get("id")), str(r.get("status", "open")))
        if current_status == "acked":
            continue
        if float(r.get("expires_at", 0)) < t:
            continue
        if args.only_open and current_status != "open":
            continue
        row = dict(r)
        row["status"] = current_status
        out.append(row)
    print(json.dumps({"ok": True, "count": len(out), "messages": out[: args.limit]}, indent=2))


def cmd_ack(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    rows = load_messages(messages_path(run_dir))
    idx = status_index(rows)
    found = any(str(r.get("id")) == args.message_id for r in rows)
    if not found:
        print(json.dumps({"ok": False, "message_id": args.message_id, "error": "message_not_found"}, indent=2))
        return
    if idx.get(args.message_id) == "acked":
        print(json.dumps({"ok": True, "message_id": args.message_id, "status": "acked"}, indent=2))
        return
    append_jsonl(
        messages_path(run_dir),
        {
            "id": str(uuid.uuid4()),
            "ts": now_ts(),
            "from": args.agent,
            "to": "council",
            "intent": "ack",
            "status": "acked",
            "ttl_sec": 3600,
            "expires_at": now_ts() + 3600,
            "payload": {"message_id": args.message_id},
            "trace_id": str(uuid.uuid4()),
        },
    )
    print(json.dumps({"ok": True, "message_id": args.message_id, "status": "acked"}, indent=2))


def cmd_claim(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    rows = load_messages(messages_path(run_dir))
    idx = status_index(rows)
    target = None
    for r in rows:
        if str(r.get("id")) == args.message_id:
            target = r
            break
    if not target:
        print(json.dumps({"ok": False, "message_id": args.message_id, "error": "message_not_found"}, indent=2))
        raise SystemExit(1)
    current_status = idx.get(args.message_id, str(target.get("status", "open")))
    if current_status != "open":
        print(json.dumps({"ok": False, "message_id": args.message_id, "status": current_status}, indent=2))
        raise SystemExit(1)
    append_jsonl(
        messages_path(run_dir),
        {
            "id": str(uuid.uuid4()),
            "ts": now_ts(),
            "from": args.agent,
            "to": "council",
            "intent": "claim",
            "status": "claimed",
            "ttl_sec": 3600,
            "expires_at": now_ts() + 3600,
            "payload": {"message_id": args.message_id},
            "trace_id": str(uuid.uuid4()),
        },
    )
    print(json.dumps({"ok": True, "message_id": args.message_id, "status": "claimed"}, indent=2))


def cmd_propose(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    st = load_state(run_dir)
    pid = args.proposal_id or str(uuid.uuid4())
    st.setdefault("decisions", {})
    st["decisions"][pid] = {
        "proposal_id": pid,
        "title": args.title,
        "proposed_by": args.agent,
        "created_at": now_ts(),
        "status": "proposed",
        "votes": {},
        "quorum": int(args.quorum) if args.quorum else int(st.get("quorum", 1)),
    }
    save_state(run_dir, st)
    append_jsonl(
        messages_path(run_dir),
        {
            "id": str(uuid.uuid4()),
            "ts": now_ts(),
            "from": args.agent,
            "to": "council",
            "intent": "proposal",
            "status": "open",
            "ttl_sec": 3600,
            "expires_at": now_ts() + 3600,
            "payload": {"proposal_id": pid, "title": args.title},
            "trace_id": str(uuid.uuid4()),
        },
    )
    print(json.dumps({"ok": True, "proposal_id": pid}, indent=2))


def cmd_vote(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    st = load_state(run_dir)
    dec = st.get("decisions", {}).get(args.proposal_id)
    if not dec:
        print(json.dumps({"ok": False, "error": "proposal_not_found"}, indent=2))
        raise SystemExit(1)
    decision = args.decision.lower()
    if decision not in {"approve", "reject", "abstain"}:
        raise SystemExit("decision must be approve|reject|abstain")
    dec.setdefault("votes", {})[args.agent] = {"decision": decision, "at": now_ts(), "note": args.note}
    approvals = sum(1 for v in dec["votes"].values() if v.get("decision") == "approve")
    rejections = sum(1 for v in dec["votes"].values() if v.get("decision") == "reject")
    quorum = int(dec.get("quorum", 1))
    if approvals >= quorum:
        dec["status"] = "resolved_approved"
        dec["resolved_at"] = now_ts()
    elif rejections >= quorum:
        dec["status"] = "resolved_rejected"
        dec["resolved_at"] = now_ts()
    else:
        dec["status"] = "voting"
    st["decisions"][args.proposal_id] = dec
    save_state(run_dir, st)
    append_jsonl(
        messages_path(run_dir),
        {
            "id": str(uuid.uuid4()),
            "ts": now_ts(),
            "from": args.agent,
            "to": "council",
            "intent": "vote",
            "status": "open",
            "ttl_sec": 3600,
            "expires_at": now_ts() + 3600,
            "payload": {"proposal_id": args.proposal_id, "decision": decision, "note": args.note},
            "trace_id": str(uuid.uuid4()),
        },
    )
    print(json.dumps({"ok": True, "proposal_id": args.proposal_id, "status": dec["status"]}, indent=2))


def cmd_resolve(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    st = load_state(run_dir)
    dec = st.get("decisions", {}).get(args.proposal_id)
    if not dec:
        print(json.dumps({"ok": False, "error": "proposal_not_found"}, indent=2))
        raise SystemExit(1)
    print(json.dumps({"ok": True, "proposal_id": args.proposal_id, "decision": dec}, indent=2))


def cmd_status(args: argparse.Namespace) -> None:
    run_dir = Path(args.run_dir).resolve()
    rows = load_messages(messages_path(run_dir))
    idx = status_index(rows)
    st = load_state(run_dir)
    t = now_ts()
    open_count = 0
    claimed_count = 0
    acked_count = 0
    expired_count = 0
    for r in rows:
        if str(r.get("intent", "")).lower() in {"ack", "claim"}:
            continue
        if float(r.get("expires_at", 0)) < t:
            expired_count += 1
            continue
        current_status = idx.get(str(r.get("id")), str(r.get("status", "open")))
        if current_status == "acked":
            acked_count += 1
        elif current_status == "claimed":
            claimed_count += 1
        else:
            open_count += 1
    print(
        json.dumps(
            {
                "ok": True,
                "total": len(rows),
                "open": open_count,
                "claimed": claimed_count,
                "acked": acked_count,
                "expired": expired_count,
                "decisions": st.get("decisions", {}),
                "quorum": st.get("quorum"),
            },
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description="Council inter-agent communication bus with quorum decisions")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init")
    p_init.add_argument("--run-dir", required=True)
    p_init.add_argument("--pattern", default="debate", choices=["voting", "debate", "hierarchical"])
    p_init.add_argument("--agents", type=int, default=4)
    p_init.add_argument("--max-rounds", type=int, default=3)
    p_init.add_argument("--quorum", type=int, default=2)
    p_init.set_defaults(func=cmd_init)

    p_send = sub.add_parser("send")
    p_send.add_argument("--run-dir", required=True)
    p_send.add_argument("--sender", required=True)
    p_send.add_argument("--receiver", required=True)
    p_send.add_argument("--intent", required=True)
    p_send.add_argument("--message", default="")
    p_send.add_argument("--payload-file")
    p_send.add_argument("--ttl-sec", type=int, default=3600)
    p_send.add_argument("--trace-id", default="")
    p_send.set_defaults(func=cmd_send)

    p_recv = sub.add_parser("recv")
    p_recv.add_argument("--run-dir", required=True)
    p_recv.add_argument("--agent", required=True)
    p_recv.add_argument("--only-open", action="store_true")
    p_recv.add_argument("--limit", type=int, default=50)
    p_recv.set_defaults(func=cmd_recv)

    p_claim = sub.add_parser("claim")
    p_claim.add_argument("--run-dir", required=True)
    p_claim.add_argument("--agent", required=True)
    p_claim.add_argument("--message-id", required=True)
    p_claim.set_defaults(func=cmd_claim)

    p_ack = sub.add_parser("ack")
    p_ack.add_argument("--run-dir", required=True)
    p_ack.add_argument("--agent", required=True)
    p_ack.add_argument("--message-id", required=True)
    p_ack.set_defaults(func=cmd_ack)

    p_prop = sub.add_parser("propose")
    p_prop.add_argument("--run-dir", required=True)
    p_prop.add_argument("--agent", required=True)
    p_prop.add_argument("--title", required=True)
    p_prop.add_argument("--proposal-id", default="")
    p_prop.add_argument("--quorum", type=int, default=0)
    p_prop.set_defaults(func=cmd_propose)

    p_vote = sub.add_parser("vote")
    p_vote.add_argument("--run-dir", required=True)
    p_vote.add_argument("--agent", required=True)
    p_vote.add_argument("--proposal-id", required=True)
    p_vote.add_argument("--decision", required=True, help="approve|reject|abstain")
    p_vote.add_argument("--note", default="")
    p_vote.set_defaults(func=cmd_vote)

    p_res = sub.add_parser("resolve")
    p_res.add_argument("--run-dir", required=True)
    p_res.add_argument("--proposal-id", required=True)
    p_res.set_defaults(func=cmd_resolve)

    p_status = sub.add_parser("status")
    p_status.add_argument("--run-dir", required=True)
    p_status.set_defaults(func=cmd_status)
    return ap


def main() -> None:
    ap = build_parser()
    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
