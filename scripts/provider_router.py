from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class ProviderSpec:
    name: str
    model: str
    # Must return output text on success, or raise on failure.
    call: Callable[[], str]
    retries: int = 0


@dataclass
class AttemptResult:
    ok: bool
    provider: str
    model: str
    duration_s: float
    error: str = ""
    text: str = ""


class CircuitBreaker:
    """
    Very small circuit-breaker persisted to <run>/state/providers.json.
    It is best-effort: it prevents repeated hammering of a provider that is failing.
    """

    def __init__(self, state_path: Path, *, open_for_s: int = 120) -> None:
        self.state_path = state_path
        self.open_for_s = int(open_for_s)

    def _load(self) -> dict[str, Any]:
        try:
            if not self.state_path.exists():
                return {}
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save(self, st: dict[str, Any]) -> None:
        try:
            self.state_path.parent.mkdir(parents=True, exist_ok=True)
            self.state_path.write_text(json.dumps(st, indent=2), encoding="utf-8")
        except Exception:
            pass

    def is_open(self, provider: str) -> bool:
        st = self._load()
        row = (st.get(provider) or {}) if isinstance(st, dict) else {}
        until = float(row.get("open_until") or 0)
        return until > time.time()

    def record_success(self, provider: str) -> None:
        st = self._load()
        st[provider] = {"open_until": 0, "last_ok": time.time(), "last_err": ""}
        self._save(st)

    def record_failure(self, provider: str, err: str) -> None:
        st = self._load()
        st[provider] = {"open_until": time.time() + self.open_for_s, "last_ok": float((st.get(provider) or {}).get("last_ok") or 0), "last_err": (err or "")[:400]}
        self._save(st)


class ProviderRouter:
    def __init__(
        self,
        *,
        circuit: Optional[CircuitBreaker] = None,
        budget_ok: Optional[Callable[[str], bool]] = None,
    ) -> None:
        self.circuit = circuit
        self.budget_ok = budget_ok

    def route(self, providers: list[ProviderSpec]) -> AttemptResult:
        last: Optional[AttemptResult] = None
        for spec in providers:
            if self.budget_ok and not self.budget_ok(spec.name):
                last = AttemptResult(ok=False, provider=spec.name, model=spec.model, duration_s=0.0, error="budget_exhausted")
                continue
            if self.circuit and self.circuit.is_open(spec.name):
                last = AttemptResult(ok=False, provider=spec.name, model=spec.model, duration_s=0.0, error="circuit_open")
                continue

            tries = max(0, int(spec.retries)) + 1
            for attempt in range(tries):
                t0 = time.time()
                try:
                    txt = spec.call()
                    res = AttemptResult(ok=True, provider=spec.name, model=spec.model, duration_s=round(time.time() - t0, 3), text=txt or "")
                    if self.circuit:
                        self.circuit.record_success(spec.name)
                    return res
                except Exception as e:
                    last = AttemptResult(
                        ok=False,
                        provider=spec.name,
                        model=spec.model,
                        duration_s=round(time.time() - t0, 3),
                        error=f"{type(e).__name__}: {e}",
                    )
                    if attempt >= tries - 1 and self.circuit:
                        self.circuit.record_failure(spec.name, last.error)
        return last or AttemptResult(ok=False, provider="", model="", duration_s=0.0, error="no_providers")

