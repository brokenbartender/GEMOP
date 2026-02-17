# Gemini-OP Command Reference

This is the consolidated command list for the current A2A + multi-agent workflow.

## 1) Repo + Sync

```powershell
git -C <REPO_ROOT> fetch --all --prune
git -C <REPO_ROOT> status --short
git -C <REPO_ROOT> pull --ff-only
```

## 2) A2A Worker Control (global utility)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File $HOME\.Gemini\a2a-tools.ps1 start
powershell -NoProfile -ExecutionPolicy Bypass -File $HOME\.Gemini\a2a-tools.ps1 status
powershell -NoProfile -ExecutionPolicy Bypass -File $HOME\.Gemini\a2a-tools.ps1 send -Peer desktop -Sender laptop -Message "ping"
powershell -NoProfile -ExecutionPolicy Bypass -File $HOME\.Gemini\a2a-tools.ps1 stop
```

## 3) A2A Ramshare + SSH Setup

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup-ssh-ramshare-permanent.ps1 -LaptopAddress <ip-or-host>
ssh Gemini-laptop echo ok
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/sync-ramshare.ps1
```

## 4) Trait Skills (100) Pipeline

```powershell
python scripts/bio_skills.py --namespace trait_skills --source-default docs/agentic-traits-100-skills.md build-registry
python scripts/bio_skills.py --namespace trait_skills --source-default docs/agentic-traits-100-skills.md validate --expected-count 100
python scripts/bio_skills.py --namespace trait_skills --source-default docs/agentic-traits-100-skills.md bootstrap-jobs --target-profile research --priority P1 --max-runtime-seconds 900
python scripts/bio_skills.py --namespace trait_skills --source-default docs/agentic-traits-100-skills.md run-all
```

## 5) Bio Skills (100) Pipeline

```powershell
python scripts/bio_skills.py build-registry --source docs/agentic-bio-100-skills.md --out ramshare/state/bio_skills/registry.json
python scripts/bio_skills.py validate --registry ramshare/state/bio_skills/registry.json --expected-count 100
python scripts/bio_skills.py bootstrap-jobs --registry ramshare/state/bio_skills/registry.json --job-inbox ramshare/state/bio_skills/inbox --target-profile research --priority P1 --max-runtime-seconds 900
python scripts/bio_skills.py run-all --registry ramshare/state/bio_skills/registry.json --job-inbox ramshare/state/bio_skills/inbox
```

## 6) Multi-Agent Batch Orchestrator (launch + scoring + learning)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/agent_batch_orchestrator.ps1 -RunDir .agent-jobs/<run-id> -MaxParallel 3 -Threshold 70
```

Learn-only on an already-completed run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/agent_batch_orchestrator.ps1 -RunDir .agent-jobs/<run-id> -NoLaunch -Threshold 70
```

## 7) Self-Learning Direct Commands

```powershell
python scripts/agent_self_learning.py score-run --run-dir .agent-jobs/<run-id>
python scripts/agent_self_learning.py learn --run-dir .agent-jobs/<run-id> --threshold 70
python scripts/agent_self_learning.py close-loop --run-dir .agent-jobs/<run-id> --threshold 70
```

## 8) Safe Full-Auto (reversible branch checkpoints)

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/safe-auto-run.ps1 -Task "your task here"
```

Optional rollback helper:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/safe-auto-rollback.ps1
```

## 9) Health + Watchdog

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/health.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-watchdog.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop-watchdog.ps1
```

## 10) Key Artifacts to Check

```text
.agent-jobs/<run-id>/learning-summary.json
ramshare/state/learning/agent_quality_scores.jsonl
ramshare/state/learning/run_summaries.jsonl
ramshare/state/learning/quality_model.json
ramshare/learning/memory/lessons.md
ramshare/notes/distilled/learning_tasks/
```

## 11) Phase 19-21 Verification (strict)

```powershell
python scripts/GEMINI_verify.py --check phase19 --strict
python scripts/GEMINI_verify.py --check phase20 --strict
python scripts/GEMINI_verify.py --check phase21 --strict
python scripts/GEMINI_verify.py --check all --strict
```

## 12) Phase 22-27 Fast Finish

```powershell
# Build or rerun a target run until threshold pass (bounded)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/phase_24_retry_loop.ps1 -RunDir .agent-jobs/<run-id> -Threshold 70 -MaxReruns 2

# End-to-end pack (retry + world model + roadmap verify)
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/phase_22_27_orchestrate.ps1 -RunDir .agent-jobs/<run-id> -Threshold 70 -MaxReruns 2

# Verify roadmap gates
python scripts/GEMINI_verify.py --check roadmap --strict
```
