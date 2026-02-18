from typing import Optional, TypedDict


class EvalMetricsSchema(TypedDict):
    rounds: int
    decision_missing_total: int
    patch_apply_ok: Optional[bool]
    verify_ok: Optional[bool]
    local_overload_hits: int
    ollama_timeouts: int
    injection_hits: int
    refusal_hits: int
    # Add other metrics as needed from RunScore


class EvalReportSchema(TypedDict):
    ok: bool
    score: float
    summary: str
    metrics: EvalMetricsSchema
    run_dir: str
    created_at: float
    online: Optional[bool]
    agents: Optional[int]
