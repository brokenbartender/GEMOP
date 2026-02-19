from __future__ import annotations

from typing import Any


TASK_CONTRACT_SCHEMA_VERSION = 1
TASK_PIPELINE_SCHEMA_VERSION = 1
TASK_PIPELINE_STAGES = {"planner", "planner_executor", "executor_verifier"}


def is_num(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def is_str_list(v: Any) -> bool:
    return isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)


def validate_task_contract_obj(obj: dict[str, Any], round_n: int) -> list[str]:
    errors: list[str] = []
    if int(obj.get("schema_version", -1)) != TASK_CONTRACT_SCHEMA_VERSION:
        errors.append("task_contract.schema_version")
    if not is_num(obj.get("generated_at")):
        errors.append("task_contract.generated_at")
    if int(obj.get("round", -1)) != int(round_n):
        errors.append("task_contract.round")
    if not isinstance(obj.get("pattern"), str):
        errors.append("task_contract.pattern")
    if not isinstance(obj.get("objective"), str) or not str(obj.get("objective")).strip():
        errors.append("task_contract.objective")
    if not isinstance(obj.get("prompt_sha256"), str):
        errors.append("task_contract.prompt_sha256")
    if not is_str_list(obj.get("constraints")):
        errors.append("task_contract.constraints")
    if not is_str_list(obj.get("deliverables")):
        errors.append("task_contract.deliverables")
    if not is_str_list(obj.get("verification")):
        errors.append("task_contract.verification")
    eh = obj.get("event_horizon")
    if not isinstance(eh, dict):
        errors.append("task_contract.event_horizon")
        return errors
    if "mass" in eh and eh.get("mass") is not None and not is_num(eh.get("mass")):
        errors.append("task_contract.event_horizon.mass")
    if not isinstance(eh.get("split_required"), bool):
        errors.append("task_contract.event_horizon.split_required")
    return errors


def validate_task_pipeline_obj(obj: dict[str, Any], round_n: int) -> list[str]:
    errors: list[str] = []
    if int(obj.get("schema_version", -1)) != TASK_PIPELINE_SCHEMA_VERSION:
        errors.append("task_pipeline.schema_version")
    if not is_num(obj.get("generated_at")):
        errors.append("task_pipeline.generated_at")
    if int(obj.get("round", -1)) != int(round_n):
        errors.append("task_pipeline.round")
    stage = obj.get("stage")
    if not isinstance(stage, str) or stage not in TASK_PIPELINE_STAGES:
        errors.append("task_pipeline.stage")
    if not isinstance(obj.get("prompt_addendum"), str) or not str(obj.get("prompt_addendum")).strip():
        errors.append("task_pipeline.prompt_addendum")
    sf = obj.get("stage_focus")
    if not isinstance(sf, dict):
        errors.append("task_pipeline.stage_focus")
        return errors
    for role in ("planner", "executor", "verifier"):
        row = sf.get(role)
        if not isinstance(row, dict):
            errors.append(f"task_pipeline.stage_focus.{role}")
            continue
        if not isinstance(row.get("goal"), str) or not str(row.get("goal")).strip():
            errors.append(f"task_pipeline.stage_focus.{role}.goal")
        if not is_str_list(row.get("required")):
            errors.append(f"task_pipeline.stage_focus.{role}.required")
        if not is_str_list(row.get("inputs")):
            errors.append(f"task_pipeline.stage_focus.{role}.inputs")
    return errors

