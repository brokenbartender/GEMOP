from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_extract_agent_decisions_uses_repair_outputs(tmp_path: Path) -> None:
    # Simulate a run dir with a non-compliant agent output and a later repair output.
    run_dir = tmp_path / "run_x"
    (run_dir / "state" / "repairs").mkdir(parents=True)

    # Main output has no DECISION_JSON.
    (run_dir / "round1_agent1.md").write_text("hello\nCOMPLETED\n", encoding="utf-8")

    repair = (
        "```json DECISION_JSON\n"
        + json.dumps(
            {
                "summary": "repair",
                "files": ["scripts/foo.py"],
                "commands": ["python -m compileall scripts"],
                "risks": ["none"],
                "confidence": 0.9,
            }
        )
        + "\n```\n"
        "COMPLETED\n"
    )
    (run_dir / "state" / "repairs" / "round1_agent1_repair1.md").write_text(repair, encoding="utf-8")

    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts" / "extract_agent_decisions.py"
    cp = subprocess.run(
        ["python", str(script), "--run-dir", str(run_dir), "--round", "1", "--agent-count", "1", "--require"],
        capture_output=True,
        text=True,
        cwd=str(repo_root),
    )
    assert cp.returncode == 0, cp.stderr

    out = json.loads((run_dir / "state" / "decisions" / "round1_agent1.json").read_text(encoding="utf-8"))
    assert out["summary"] == "repair"
    assert "source_path" in out
    assert out["source_path"].endswith("round1_agent1_repair1.md")

