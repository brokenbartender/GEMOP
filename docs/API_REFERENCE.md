# API Reference

## a2a_bridge_ssh.py

*No documentation provided.*

## a2a_bridge_wsl.py

*No documentation provided.*

## a2a_doctor.ps1

*No documentation provided.*

## a2a_receive.py

*No documentation provided.*

## a2a_remote_executor.py

*No documentation provided.*

## a2a_router.py

*No documentation provided.*

## achilles_simulate.py

Scans Python code for destructive patterns using AST.

## action_ledger.py

*No documentation provided.*

## adaptive_concurrency.py

*No documentation provided.*

## agent_capability_broker.py

Parses agent output for capability request blocks.

## agent_cards.py

*No documentation provided.*

## agent_curator.py

*No documentation provided.*

## agent_efficiency_learner.py

*No documentation provided.*

## agent_evaluator_template.py

agent_evaluator_template.py

A conceptual template for automated, multi-turn AI agent evaluation.
This script demonstrates the structure for evaluating agents that perform
multi-step tasks, use tools, and modify state, reflecting 2026 best practices.

References:
- Anthropic. (2026, January 9). Demystifying evals for AI agents.
https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents

## agent_foundry.py

You are the Agent Foundry. Your job is to analyze a mission prompt and select the optimal team of specialist agents.
Available agents: architect, engineer, tester, researcher, security_officer, data_analyst, ChiefOfStaff, CouncilFacilitator, DocSpecialist.
Respond with a single line: MISSION_TEAM: <agent1>, <agent2>, ...
Example: MISSION_TEAM: architect, engineer, tester

## agent_host.py

Best-effort Windows Job Object container. Returns a handle int or None.
If job creation fails, caller should fall back to normal subprocess behavior.

## agent_output_validator.py

*No documentation provided.*

## agent_pack_generate.py

$ErrorActionPreference = 'Stop'
$repo = '{repo}'
$prompt = Join-Path $PSScriptRoot 'prompt{index}.txt'
$roundOut = Join-Path $PSScriptRoot 'round1_agent{index}.md'
$finalOut = Join-Path $PSScriptRoot 'agent{index}.md'
python (Join-Path $repo 'scripts\\agent_runner_v2.py') $prompt $roundOut
if (Test-Path -LiteralPath $roundOut) {{
Copy-Item -LiteralPath $roundOut -Destination $finalOut -Force
}}

## agent_runner_v2.py

Raised when local inference is intentionally refused to protect the host.

## agent_self_learning.py

*No documentation provided.*

## ai_data_factory.py

*No documentation provided.*

## ai_ops_report.py

*No documentation provided.*

## analyze_png_lineart.py

*No documentation provided.*

## approve_action.py

*No documentation provided.*

## art_syndicate_run.py

*No documentation provided.*

## auto_cleanup.py

*No documentation provided.*

## batch_improve_cycles.ps1

Run N improvement cycles. Each cycle uses improve_until_100.ps1 to reach 100/100 (or best effort),
records the best run dir, then produces a batch summary at the end.

## build-context.ps1

*No documentation provided.*

## chaos_monkey.py

*No documentation provided.*

## chat_bridge.py

*No documentation provided.*

## check_docs.ps1

*No documentation provided.*

## chronobio_consolidation.py

*No documentation provided.*

## cleanup_local.ps1

*No documentation provided.*

## commit-with-communication.ps1

.SYNOPSIS
Creates a structured commit message and commits it.

.DESCRIPTION
Writes a commit message to .git\COMMIT_EDITMSG.auto and runs `git commit -F`.
Designed for consistent operator-to-operator communication.

NOTE: This script does not log the message content (to avoid accidental leakage
of sensitive context). It only logs high-level status.

## config_assemble.py

*No documentation provided.*

## config_loader.py

Loads the unified ecosystem_state.yaml.

## contract_repair.py

*No documentation provided.*

## council_bus.py

Emit a digital pheromone (low-overhead signaling).

## council_patch_apply.py

Extracts (path, content) from ```file path ... ``` blocks.

## council_reflection_learner.py

*No documentation provided.*

## council_scorecard.py

*No documentation provided.*

## council_supervisor.py

Heuristic scan for "shadow code" attempts: diffs that weaken guardrails.
Returns a list of findings (each includes file + line).

## dark_matter_halo.py

*No documentation provided.*

## dashboard.py

<style>
.stApp { background-color: #050505; color: #e0e0e0; }
.stMetric { background-color: #111; border: 1px solid #333; padding: 10px; border-radius: 10px; }
.stButton>button { border-radius: 8px; font-weight: 600; }
.status-thinking { color: #3b82f6; animation: pulse 2s infinite; }
@keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
</style>

## deputy_chat_processor.py

*No documentation provided.*

## distill.ps1

*No documentation provided.*

## djed_heartbeat.ps1

.SYNOPSIS
The Djed Pillar: Stability & Heartbeat Monitor.
Continuously pings the active run to ensure the spine doesn't snap.

## eval_harness.py

Returns (rounds_seen, missing_total) based on state/decisions_round*.json.

## event_horizon_scheduler.py

*No documentation provided.*

## evidence_chain.py

*No documentation provided.*

## extract-docs.py

Extract lightweight text from PDFs/HTML snapshots into plain text.

This exists to make downstream semantic indexing fast and deterministic:
- Avoid re-downloading or re-parsing large PDFs during interactive sessions.
- Keep extraction logic simple and dependency-light.

## extract_agent_decisions.py

"Atomic agent" reliability:
- Strict-ish JSON contract so orchestration can be deterministic.
- Treat invalid contract as missing (so contract_repair can fix it).

## fengshen_registry.py

Creates the Fengshen Bang (Registry of Sealed Gods).
Assigns strict offices and powers to each agent.

## fidelity_council.ps1

.SYNOPSIS
Run a finance-focused council debate for Fidelity portfolio prompts.

.DESCRIPTION
Thin wrapper around scripts/summon.ps1 with defaults tuned for
market/event research quality:
- disables generic auto-skill injection
- enables online research
- deepens query coverage for macro + ticker catalysts

## fidelity_intake.py

*No documentation provided.*

## finance_council_run.py

*No documentation provided.*

## formal_verifier.py

Axiom 1: All mutations must remain within the Mosaic (repo sandbox).

## gemini_a2a_send.py

*No documentation provided.*

## gemini_a2a_send_structured.py

*No documentation provided.*

## gemini_budget.py

*No documentation provided.*

## gemini_dispatcher.py

*No documentation provided.*

## gemini_governance.py

Return False if the global kill switch is enabled.

## gemini_heartbeat.py

Appends a message to the debug log.

## gemini_hud.py

*No documentation provided.*

## gemini_preflight.py

*No documentation provided.*

## gemini_presets.py

*No documentation provided.*

## gemini_smart.py

*No documentation provided.*

## gemini_task.py

*No documentation provided.*

## gemini_tool_selector.py

*No documentation provided.*

## gemini_verify.py

*No documentation provided.*

## gemini_watchdog.py

*No documentation provided.*

## generate_api_docs.py

Extracts docstrings from a Python or PowerShell file.

## generate_eval_report.py

*No documentation provided.*

## governance_gate.py

*No documentation provided.*

## gravity_well.py

Calculates the 'Semantic Mass' of memory blocks.
Heavier mass = Higher relevance to the anchor.

## gyro_context.py

The Egg of Columbus: Gyroscopic Context Stabilization.
Spins the context to make the 'Task' stand upright.

## hawking_emitter.py

*No documentation provided.*

## health.ps1

*No documentation provided.*

## health_reporter.py

Runs the PowerShell health check script and returns its JSON output.

## heraclean_test_suite.ps1

.SYNOPSIS
The Heraclean Test Suite: 10 Rigorous Labors for Gemini OP.
Validates Physics, Governance, and Orchestration layers.

## higgs_field.py

Assigns 'Mass' (Validity Weight) to a parallel solution.

## hlidskjalf_dashboard.py

<style>
.stApp { background-color: #0a0a0a; color: #00ff00; font-family: 'Courier New', Courier, monospace; }
.sigil-card { border: 2px solid #00ff00; padding: 20px; border-radius: 50%; width: 200px; height: 200px; text-align: center; display: flex; flex-direction: column; justify-content: center; align-items: center; margin: 10px; box-shadow: 0 0 15px #00ff00; }
.tarot-card { border: 1px solid #ff00ff; padding: 10px; border-radius: 5px; background-color: #1a001a; text-align: center; color: #ff00ff; box-shadow: 0 0 5px #ff00ff; }
.circuit-active { animation: pulse 1s infinite; color: #fff; text-shadow: 0 0 10px #00ff00; }
@keyframes pulse { 0% { transform: scale(1); } 50% { transform: scale(1.05); } 100% { transform: scale(1); } }
</style>

## hubble_drift.py

*No documentation provided.*

## improve_until_100.ps1

Repeat Council runs until the scorecard reaches 100/100 (process + patch), or until MaxAttempts.

This is intentionally conservative:
- It does not force destructive actions.
- It keeps Agents=3 by default for CPU-only machines.

## ingest-and-index.ps1

*No documentation provided.*

## interactive_chat.py

*No documentation provided.*

## iolaus_cauterize.py

Scans pids.json for 'Hydra heads' or kills specific Lyapunov-diverged threads.
Applies fire (SIGKILL) to prevent recursive system collapse.

## killswitch.py

*No documentation provided.*

## legal_testgen.py

*No documentation provided.*

## lotus_pruner.py

Induces 'Lotus Forgetfulness' by moving old round artifacts to a
'.lotus_history' folder to keep the active context window clean.

## mana_ranker.py

Analyzes the learning summary and updates agent Mana (Trust Scores).

## manifest_router.py

"Service Router" concept: decouple workflow (roles) from intelligence (models/providers).
This is a lightweight, repo-native config that agent_runner_v2 can consult.

## market_theme_run.py

*No documentation provided.*

## marketplace_image_check.py

*No documentation provided.*

## maxwells_demon.py

Maxwell's Demon: Artificially lowers entropy by deleting filler.

## mem1_consolidator.py

You are the MEM1 State Consolidator.
CURRENT INTERNAL STATE:
{current_state}

NEW UPDATES FROM ROUND {round_n}:
{chr(10).join(['- ' + u for u in updates])}

TASK:
Synthesize the current state and new updates into a single, compact, cohesive paragraph (max 150 words).
Preserve all critical technical decisions and file paths.
Output ONLY the synthesized paragraph.

## memory-ingest.ps1

*No documentation provided.*

## memory_ingest.py

*No documentation provided.*

## memory_manager.py

CREATE TABLE IF NOT EXISTS cache (
key TEXT PRIMARY KEY,
value TEXT,
expires_at REAL
)

## myth_runtime.py

*No documentation provided.*

## nightly_ops.ps1

*No documentation provided.*

## nuclear_reset.ps1

*No documentation provided.*

## observer_daemon.py

[ANTICIPATORY COMPUTING MODE]
You are the Observer Agent. The user is actively working on these files:
{json.dumps(changed_files, indent=2)}

TASK:
Infer the user's current focus and intent.
Output a valid JSON object with the current context state.

OUTPUT JSON:
{{
"current_focus": "One sentence summary",
"inferred_intent": "What they are trying to achieve",
"proactive_suggestion": "A high-value task we could offer to do (or null if none)"
}}

## olympus_backend.py

Manages the real-time WebSocket connections for the Goetic Swarm.

## olympus_console.py

<style>
.stApp { background-color: #050505; color: #d4af37; font-family: 'serif'; }
.cerberus-gate { border: 2px solid #8b0000; padding: 15px; border-radius: 10px; background: rgba(139,0,0,0.1); }
.hydra-node { border: 2px solid #d4af37; padding: 10px; border-radius: 50%; text-align: center; box-shadow: 0 0 10px #d4af37; }
.augean-flow { border-left: 3px solid #00ced1; padding-left: 20px; color: #e0e0e0; }
.titan-toggle { font-size: 2em; font-weight: bold; color: #ff4500; }
.tarot-card { border: 1px solid #ff00ff; padding: 5px; border-radius: 5px; background: #1a001a; margin-bottom: 5px; }
</style>

## omni_god_mode.ps1

*No documentation provided.*

## omnimodal_mediator.py

*No documentation provided.*

## optimize-workspace-layout.ps1

*No documentation provided.*

## phase6_schema.py

*No documentation provided.*

## phase_24_retry_loop.ps1

.SYNOPSIS
Retry loop wrapper around the triad orchestrator.

## procrustes_normalize.py

Enforces the 'Bed of Procrustes' on input data.
Truncates if too long, pads with metadata if too short.

## promote-plan-updates.ps1

*No documentation provided.*

## provider_router.py

Very small circuit-breaker persisted to <run>/state/providers.json.
It is best-effort: it prevents repeated hammering of a provider that is failing.

## pull-ramshare-from-server.ps1

*No documentation provided.*

## pull-resources.ps1

*No documentation provided.*

## quantum_state.py

Spawns a single parallel reality (agent thread).

## rb_catalog_scan.py

*No documentation provided.*

## rb_lineart_generator.py

*No documentation provided.*

## rb_photo_to_style.py

*No documentation provided.*

## rb_preflight.py

*No documentation provided.*

## rb_stickerize.py

*No documentation provided.*

## rb_style_cycle.py

*No documentation provided.*

## rb_style_train.py

*No documentation provided.*

## rb_upload_packet.py

*No documentation provided.*

## recursive_meta_agent.py

[SYSTEM EVOLUTION MODE]
You are the Meta-Agent responsible for evolving the system's operating constraints.

RECENT FAILURES:
{error_context}

CURRENT POLICY:
{(policy_path.read_text() if policy_path.exists() else "{}")}

TASK:
Generate a new, specific global constraint or hint to prevent these failures.
Focus on prompt engineering fixes (e.g., "Agents must verify X before Y").

OUTPUT JSON ONLY:
{{
"new_constraint": "The concise rule to add",
"reason": "Why this fixes the failure"
}}

## redbubble_pipeline_run.py

*No documentation provided.*

## redbubble_profit_harness.py

*No documentation provided.*

## ren_guardian.py

Calculates the cryptographic 'True Name' hash of the system prompt.

## repo_index.py

*No documentation provided.*

## repo_paths.py

Resolve the repository root.

Priority:
1) GEMINI_OP_REPO_ROOT (set by start.ps1 and other launchers)
2) this file's location (repo/scripts/repo_paths.py -> parents[1])

## request-other-computer-info.ps1

*No documentation provided.*

## resonator_stress.py

The Earthquake Machine: Pulses the system with variable input frequencies
to find the 'Shudder Point' (Hallucination/Failure).

## retrieval_pack.py

*No documentation provided.*

## rlhf_logger.py

*No documentation provided.*

## run_council_detached.ps1

.SYNOPSIS
Robust council launcher that avoids command-line quoting issues.

.DESCRIPTION
Use this script when you need to run a council with a long prompt that includes spaces,
quotes, or PowerShell metacharacters (like '&'). Provide the prompt via -PromptFile.

This script is safe to run directly or via Start-Process for detached execution.

## run_status.py

*No documentation provided.*

## safe-auto-rollback.ps1

.SYNOPSIS
Rolls back a safe-auto run to the recorded base branch state.

.DESCRIPTION
Loads .safe-auto\runs\<RunId>\state.json and resets the repository back to the
base branch and remote recorded at run start. Optionally deletes the run branch.

This script waits for git lock files and uses safe file paths.

## safe-auto-run.ps1

.SYNOPSIS
Runs Gemini in a guarded, checkpointed git workflow.

.DESCRIPTION
Creates a new run branch, periodically checkpoints any working tree changes,
pushes and verifies the remote HEAD, and records artifacts in .safe-auto\runs.

This script is intended to be safe-by-default:
- waits for git locks (index.lock, etc.)
- avoids logging common secret patterns
- uses file-safe paths via Join-Path

## scan_risk.py

*No documentation provided.*

## scan_secrets.py

*No documentation provided.*

## self_improve_loop.ps1

*No documentation provided.*

## set-policy-mode.ps1

*No documentation provided.*

## setup-git-commit-policy.ps1

*No documentation provided.*

## setup-laptop-workstation.ps1

*No documentation provided.*

## setup-sidecar.ps1

*No documentation provided.*

## setup-ssh-ramshare-permanent.ps1

*No documentation provided.*

## signet_verifier.py

Placeholder for Signet Verification logic.
In a full implementation, this calls a high-reasoning LLM (like Gemini 1.5 Pro)
to verify that the code changes actually fulfill the intent of the prompt
and do not introduce "Demonic" (malicious/unwanted) side effects.

## skill_bridge.py

*No documentation provided.*

## smart_summon.ps1

.SYNOPSIS
Smart wrapper for summon.ps1 that dynamically compiles the best agent team.

.DESCRIPTION
Analyzes the task prompt using `team_compiler.py` to select specialized roles
(e.g. ResearchLead, Security, Ops) instead of the default Triad.
Then invokes `summon.ps1` with the optimized team.

.EXAMPLE
.\scripts\smart_summon.ps1 -Task "Research competitors and draft a strategy doc"

## sovereign.py

Sovereign: The Unified Cortex for Gemini OP.
Cohesively integrates Swarm, Finance, Commerce, and Governance subsystems.

## spirit_radio.py

Continuous background latency sensor.
Listens to the 'Static' in the network.

## start-a2a-executor-wsl.ps1

*No documentation provided.*

## start-sidecar.ps1

*No documentation provided.*

## start-watchdog.ps1

*No documentation provided.*

## start_local_stack.ps1

Error reading scripts\start_local_stack.ps1: 'utf-8' codec can't decode byte 0xff in position 0: invalid start byte

## state_rebuilder.py

*No documentation provided.*

## stop-sidecar.ps1

*No documentation provided.*

## stop-watchdog.ps1

*No documentation provided.*

## stop_agents.ps1

.SYNOPSIS
Stop currently-running Gemini-OP agent processes (best-effort) and set STOP flags.

.DESCRIPTION
This is the "killswitch" operators should use before starting a fresh council run.
It works in two layers:
1) Write STOP files that cooperative agents check.
2) Best-effort terminate processes whose command line appears to reference this repo and agent runner scripts.

This script is intentionally conservative: it targets only processes that reference the repo root (or repo folder name)
in the command line to avoid killing unrelated shells.

## summarize_batch.py

*No documentation provided.*

## summon.ps1

.SYNOPSIS
Summon a council run from a single task prompt, with automatic skill selection.

.DESCRIPTION
Creates a new run directory under .agent-jobs/ and launches scripts/triad_orchestrator.ps1
with safe, high-power defaults:
- stop prior agents
- decision extraction + verify-friendly output contract
- optional hybrid routing via -Online
- auto-selected external skills (Codex + Gemini) injected into prompts

This script is the recommended "do whatever I want" entrypoint.

## sync-ramshare.ps1

*No documentation provided.*

## system_metrics.py

Cross-platform-ish memory info. On Windows, uses GlobalMemoryStatusEx (no deps).
On other platforms, returns 0s (best-effort).

## system_qa_check.py

*No documentation provided.*

## tarot_telemetry.py

Heuristic Warning Engine.
Interprets raw signals into 'Fates' (System Events).

## task_contract.py

*No documentation provided.*

## task_pipeline.py

*No documentation provided.*

## team_compiler.py

*No documentation provided.*

## telluric_resonance.py

Attempt to get CPU temperature (Platform dependent).

## tesla_valve.py

The Tesla Valve: Ensures logic flows Forward (Premise -> Conclusion).
Blocks Reverse Flow (Conclusion -> Premise).

## test_memory_vector.py

*No documentation provided.*

## thermodynamics.py

S = k * ln(Omega)
Measures 'Confusion' in the context.

## throttle-agent-workers.ps1

*No documentation provided.*

## tool_registry.py

*No documentation provided.*

## triad_orchestrator.ps1

.SYNOPSIS
Gemini-OP council orchestrator (canonical multi-agent engine).

.DESCRIPTION
This orchestrator is the "run directory" engine used by:
- scripts/phase_24_retry_loop.ps1
- scripts/phase_22_27_orchestrate.ps1
- scripts/self_improve_loop.ps1
- start.ps1 -Council (alias: -Triad)

It supports two modes:
1) Existing run dir: if RunDir already contains run-agent*.ps1, it will execute them (throttled).
2) Generated run dir: if RunDir is missing run-agent scripts, it will generate prompt*.txt + run-agent*.ps1
and execute them using scripts/agent_runner_v2.py.

After execution it writes:
- learning-summary.json (in the run dir)
and can fail closed on a score threshold.

## triad_orchestrator_FIX.ps1

*No documentation provided.*

## update_app_status.py

*No documentation provided.*

## validate_phase6_contracts.py

*No documentation provided.*

## validate_tool_contracts.py

Smoke-check tool contract types and basic schema shape.

This is intentionally lightweight: it should run fast and from any working
directory (Council runs, patch-apply verification, CI, etc.).

## verify_evidence_chain.py

*No documentation provided.*

## verify_pipeline.py

*No documentation provided.*

## wampum_ledger.py

Records a decision as an immutable Wampum Treaty.

## watch-evidence.ps1

*No documentation provided.*

## web_research_fetch.py

*No documentation provided.*

## web_research_search.py

*No documentation provided.*

## world_model_snapshot.py

*No documentation provided.*

## wormhole_indexer.py

Creates zero-latency shortcuts between conceptually linked files.

## yeet.ps1

.SYNOPSIS
Safely stages, commits, and pushes changes to a specific target repository with Signet Verification.

## zhinan_alignment.py

Placeholder for Zhinan Alignment logic.
In a full implementation, this uses a specialized 'Compass' LLM
to calculate the semantic distance between the current state
and the original mission objective.

