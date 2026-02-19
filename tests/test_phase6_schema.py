from __future__ import annotations

import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from phase6_schema import (
    TASK_CONTRACT_SCHEMA_VERSION,
    TASK_PIPELINE_SCHEMA_VERSION,
    TASK_RANK_SCHEMA_VERSION,
    validate_task_contract_obj,
    validate_task_pipeline_obj,
    validate_task_rank_obj,
)


class Phase6SchemaTests(unittest.TestCase):
    def test_validate_task_contract_obj_accepts_valid_payload(self) -> None:
        payload = {
            "schema_version": TASK_CONTRACT_SCHEMA_VERSION,
            "generated_at": 1.0,
            "pattern": "debate",
            "round": 2,
            "max_rounds": 3,
            "prompt_sha256": "abc",
            "objective": "Do thing",
            "constraints": ["must be safe"],
            "deliverables": ["update file"],
            "verification": ["python -m pytest -q tests"],
            "event_horizon": {"mass": 2.5, "split_required": False},
        }
        errors = validate_task_contract_obj(payload, 2)
        self.assertEqual(errors, [])

    def test_validate_task_pipeline_obj_flags_missing_inputs(self) -> None:
        payload = {
            "schema_version": TASK_PIPELINE_SCHEMA_VERSION,
            "generated_at": 1.0,
            "pattern": "debate",
            "round": 1,
            "stage": "planner",
            "prompt_addendum": "x",
            "stage_focus": {
                "planner": {"goal": "x", "required": ["a"]},
                "executor": {"goal": "x", "required": ["a"]},
                "verifier": {"goal": "x", "required": ["a"]},
            },
        }
        errors = validate_task_pipeline_obj(payload, 1)
        self.assertTrue(any(e.endswith(".inputs") for e in errors))

    def test_validate_task_rank_obj_accepts_valid_payload(self) -> None:
        payload = {
            "schema_version": TASK_RANK_SCHEMA_VERSION,
            "generated_at": 1.0,
            "method": "deterministic_v1",
            "round": 2,
            "agent_count": 2,
            "top_agent": 1,
            "rankings": [
                {
                    "agent": 1,
                    "score": 90,
                    "supervisor_score": 82,
                    "status": "OK",
                    "has_decision_json": True,
                    "has_diff": True,
                    "completed": True,
                }
            ],
        }
        errors = validate_task_rank_obj(payload, 2)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
