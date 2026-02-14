from __future__ import annotations

import argparse
import json
import os
import subprocess
import urllib.request
from pathlib import Path
from typing import Any, Dict, List


def verify_exists(path: str) -> Dict[str, Any]:
    return {"type": "exists", "path": path, "ok": os.path.exists(path)}


def verify_http(url: str, timeout: int = 5) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return {"type": "http", "url": url, "ok": resp.status == 200, "status": resp.status}
    except Exception as exc:
        return {"type": "http", "url": url, "ok": False, "error": str(exc)}


def verify_contract(contract: Dict[str, Any]) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []
    for p in contract.get("required_files", []):
        checks.append(verify_exists(str(p)))
    for u in contract.get("required_urls", []):
        checks.append(verify_http(str(u), timeout=int(contract.get("http_timeout", 5))))

    pass_required = all(bool(c.get("ok")) for c in checks)
    result = {
        "type": "contract",
        "ok": pass_required,
        "checks": checks,
        "required_files": contract.get("required_files", []),
        "required_urls": contract.get("required_urls", []),
    }
    return result


def verify_phase21() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    chronobio = repo_root / "scripts" / "chronobio_consolidation.py"
    watchdog = repo_root / "scripts" / "GEMINI_watchdog.py"
    ingest = repo_root / "scripts" / "memory-ingest.ps1"
    checks: List[Dict[str, Any]] = [
        verify_exists(str(chronobio)),
        verify_exists(str(watchdog)),
        verify_exists(str(ingest)),
    ]

    if chronobio.exists():
        try:
            proc = subprocess.run(
                ["python", str(chronobio), "--plan"],
                cwd=str(repo_root),
                capture_output=True,
                text=True,
            )
            ok = proc.returncode == 0
            payload_ok = False
            if ok:
                try:
                    parsed = json.loads(proc.stdout or "{}")
                    payload_ok = isinstance(parsed.get("steps"), list) and len(parsed["steps"]) > 0
                except Exception:
                    payload_ok = False
            checks.append(
                {
                    "type": "phase21_plan",
                    "ok": ok and payload_ok,
                    "returncode": proc.returncode,
                    "stdout_tail": (proc.stdout or "")[-1200:],
                    "stderr_tail": (proc.stderr or "")[-1200:],
                }
            )
        except Exception as exc:
            checks.append({"type": "phase21_plan", "ok": False, "error": str(exc)})

    return {"type": "phase21", "ok": all(c.get("ok", False) for c in checks), "checks": checks}


def _contains_all(path: Path, terms: List[str]) -> Dict[str, Any]:
    if not path.exists():
        return {"ok": False, "missing_file": str(path), "terms": terms}
    text = path.read_text(encoding="utf-8", errors="ignore").lower()
    found = {t: (t.lower() in text) for t in terms}
    return {"ok": all(found.values()), "found": found}


def verify_phase22() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    orchestrator = repo_root / "scripts" / "agent_batch_orchestrator.ps1"
    council = repo_root / "scripts" / "council_reflection_learner.py"
    checks: List[Dict[str, Any]] = [
        verify_exists(str(orchestrator)),
        verify_exists(str(council)),
    ]
    checks.append(
        {
            "type": "phase22_orchestrator_contract",
            **_contains_all(
                orchestrator,
                ["RequireCouncilDiscussion", "Council Communication Contract", "Inject-CouncilProtocolContract"],
            ),
        }
    )
    checks.append(
        {
            "type": "phase22_council_contract",
            **_contains_all(council, ["council_protocol_not_followed"]),
        }
    )
    return {"type": "phase22", "ok": all(c.get("ok", False) for c in checks), "checks": checks}


def verify_phase23() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    broker = repo_root / "scripts" / "agent_capability_broker.py"
    orchestrator = repo_root / "scripts" / "agent_batch_orchestrator.ps1"
    checks: List[Dict[str, Any]] = [
        verify_exists(str(broker)),
        verify_exists(str(orchestrator)),
    ]
    checks.append(
        {
            "type": "phase23_broker_contract",
            **_contains_all(broker, ["--auto-apply-mcp", "capability-catalog.json", "new_acquired"]),
        }
    )
    checks.append(
        {
            "type": "phase23_orchestrator_broker_integration",
            **_contains_all(orchestrator, ["capability broker", "capability-catalog.md"]),
        }
    )
    return {"type": "phase23", "ok": all(c.get("ok", False) for c in checks), "checks": checks}


def verify_phase24() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    retry = repo_root / "scripts" / "phase_24_retry_loop.ps1"
    learning = repo_root / "scripts" / "agent_self_learning.py"
    checks: List[Dict[str, Any]] = [
        verify_exists(str(retry)),
        verify_exists(str(learning)),
    ]
    checks.append({"type": "phase24_retry_contract", **_contains_all(retry, ["MaxReruns", "avg_score", "Threshold"])})
    checks.append(
        {
            "type": "phase24_learning_contract",
            **_contains_all(learning, ["close-loop", "prompt_hints", "tasks_added"]),
        }
    )
    return {"type": "phase24", "ok": all(c.get("ok", False) for c in checks), "checks": checks}


def verify_phase25() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    router = repo_root / "scripts" / "a2a_router.py"
    bridge = repo_root / "scripts" / "a2a_bridge_ssh.py"
    sender = repo_root / "scripts" / "GEMINI_a2a_send_structured.py"
    checks: List[Dict[str, Any]] = [
        verify_exists(str(router)),
        verify_exists(str(bridge)),
        verify_exists(str(sender)),
    ]
    checks.append({"type": "phase25_router_cluster_contract", **_contains_all(router, ["outbox", "dlq", "idempotency"])})
    return {"type": "phase25", "ok": all(c.get("ok", False) for c in checks), "checks": checks}


def verify_phase26() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    safe = repo_root / "scripts" / "safe-auto-run.ps1"
    checks: List[Dict[str, Any]] = [verify_exists(str(safe))]
    checks.append(
        {
            "type": "phase26_safe_auto_contract",
            **_contains_all(safe, ["checkpoint", "push verify", "state.json", "governance gate"]),
        }
    )
    return {"type": "phase26", "ok": all(c.get("ok", False) for c in checks), "checks": checks}


def verify_phase27() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    world_script = repo_root / "scripts" / "world_model_snapshot.py"
    world_file = repo_root / "ramshare" / "state" / "world_model" / "latest.json"
    checks: List[Dict[str, Any]] = [verify_exists(str(world_script))]
    if world_script.exists():
        try:
            proc = subprocess.run(["python", str(world_script), "--refresh"], cwd=str(repo_root), capture_output=True, text=True)
            checks.append(
                {
                    "type": "phase27_refresh",
                    "ok": proc.returncode == 0,
                    "returncode": proc.returncode,
                    "stdout_tail": (proc.stdout or "")[-800:],
                    "stderr_tail": (proc.stderr or "")[-800:],
                }
            )
        except Exception as exc:
            checks.append({"type": "phase27_refresh", "ok": False, "error": str(exc)})
    checks.append(verify_exists(str(world_file)))
    if world_file.exists():
        try:
            payload = json.loads(world_file.read_text(encoding="utf-8-sig"))
            checks.append(
                {
                    "type": "phase27_snapshot_shape",
                    "ok": isinstance(payload, dict) and isinstance(payload.get("health"), dict),
                    "keys": sorted(list(payload.keys()))[:20] if isinstance(payload, dict) else [],
                }
            )
        except Exception as exc:
            checks.append({"type": "phase27_snapshot_shape", "ok": False, "error": str(exc)})
    return {"type": "phase27", "ok": all(c.get("ok", False) for c in checks), "checks": checks}


def verify_phase19() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    router = repo_root / "scripts" / "a2a_router.py"
    idempotency = repo_root / "ramshare" / "state" / "a2a" / "idempotency.json"
    checks: List[Dict[str, Any]] = [
        verify_exists(str(router)),
        verify_exists(str(idempotency)),
    ]

    if router.exists():
        text = router.read_text(encoding="utf-8", errors="ignore").lower()
        has_idempot = "idempot" in text
        has_replay_or_duplicate = ("replay" in text) or ("duplicate_task_id" in text) or ("mark_or_reject_task" in text)
        checks.append(
            {
                "type": "phase19_router_contract",
                "ok": has_idempot and has_replay_or_duplicate,
                "has_idempot": has_idempot,
                "has_replay_or_duplicate": has_replay_or_duplicate,
            }
        )
    if idempotency.exists():
        try:
            payload = json.loads(idempotency.read_text(encoding="utf-8-sig"))
            checks.append(
                {
                    "type": "phase19_idempotency_state",
                    "ok": isinstance(payload, dict),
                    "keys": sorted(list(payload.keys()))[:20],
                }
            )
        except Exception as exc:
            checks.append({"type": "phase19_idempotency_state", "ok": False, "error": str(exc)})

    return {"type": "phase19", "ok": all(c.get("ok", False) for c in checks), "checks": checks}


def verify_phase20() -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parents[1]
    governance = repo_root / "scripts" / "GEMINI_governance.py"
    dispatcher = repo_root / "scripts" / "GEMINI_dispatcher.py"
    budgets = repo_root / "ramshare" / "state" / "governance" / "agent_budgets.json"
    checks: List[Dict[str, Any]] = [
        verify_exists(str(governance)),
        verify_exists(str(dispatcher)),
        verify_exists(str(budgets)),
    ]

    if governance.exists():
        text = governance.read_text(encoding="utf-8", errors="ignore").lower()
        checks.append(
            {
                "type": "phase20_governance_contract",
                "ok": ("agent-budget" in text) or ("agent_budget" in text),
            }
        )
    if dispatcher.exists():
        text = dispatcher.read_text(encoding="utf-8", errors="ignore").lower()
        checks.append(
            {
                "type": "phase20_dispatcher_contract",
                "ok": ("score" in text) and ("fair" in text),
            }
        )
    if budgets.exists():
        try:
            payload = json.loads(budgets.read_text(encoding="utf-8-sig"))
            checks.append(
                {
                    "type": "phase20_budget_state",
                    "ok": isinstance(payload, dict) and len(payload) > 0,
                    "agents": sorted(list(payload.keys()))[:20] if isinstance(payload, dict) else [],
                }
            )
        except Exception as exc:
            checks.append({"type": "phase20_budget_state", "ok": False, "error": str(exc)})

    return {"type": "phase20", "ok": all(c.get("ok", False) for c in checks), "checks": checks}


def main() -> None:
    ap = argparse.ArgumentParser(description="Gemini verification helpers")
    ap.add_argument("--exists", help="Check if a file exists")
    ap.add_argument("--http", help="Check an HTTP URL")
    ap.add_argument("--contract-file", help="JSON file with required_files/required_urls")
    ap.add_argument(
        "--check",
        choices=[
            "phase19",
            "phase20",
            "phase21",
            "phase22",
            "phase23",
            "phase24",
            "phase25",
            "phase26",
            "phase27",
            "all",
            "roadmap",
        ],
        help="Run built-in verification bundle",
    )
    ap.add_argument("--strict", action="store_true", help="Return non-zero exit when verification fails")
    args = ap.parse_args()

    if args.exists:
        out = verify_exists(args.exists)
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return

    if args.http:
        out = verify_http(args.http)
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return

    if args.contract_file:
        contract_path = Path(args.contract_file).expanduser().resolve()
        if not contract_path.exists():
            raise SystemExit(f"contract file not found: {contract_path}")
        contract = json.loads(contract_path.read_text(encoding="utf-8-sig"))
        out = verify_contract(contract)
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return

    if args.check == "phase21":
        out = verify_phase21()
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return
    if args.check == "phase19":
        out = verify_phase19()
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return
    if args.check == "phase20":
        out = verify_phase20()
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return
    if args.check == "all":
        phase19 = verify_phase19()
        phase20 = verify_phase20()
        phase21 = verify_phase21()
        out = {
            "type": "all",
            "ok": bool(phase19.get("ok")) and bool(phase20.get("ok")) and bool(phase21.get("ok")),
            "checks": [phase19, phase20, phase21],
        }
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return
    if args.check == "phase22":
        out = verify_phase22()
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return
    if args.check == "phase23":
        out = verify_phase23()
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return
    if args.check == "phase24":
        out = verify_phase24()
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return
    if args.check == "phase25":
        out = verify_phase25()
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return
    if args.check == "phase26":
        out = verify_phase26()
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return
    if args.check == "phase27":
        out = verify_phase27()
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return
    if args.check == "roadmap":
        bundles = [
            verify_phase22(),
            verify_phase23(),
            verify_phase24(),
            verify_phase25(),
            verify_phase26(),
            verify_phase27(),
        ]
        out = {"type": "roadmap", "ok": all(b.get("ok", False) for b in bundles), "checks": bundles}
        print(json.dumps(out, indent=2))
        if args.strict and not out["ok"]:
            raise SystemExit(2)
        return

    print(json.dumps({"ok": False, "error": "no verification mode specified"}, indent=2))
    raise SystemExit(1)


if __name__ == "__main__":
    main()
