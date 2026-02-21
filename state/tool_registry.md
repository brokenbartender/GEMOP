# Tool Registry

generated_at: 1771613909.995019

- `summon`: One-line council launcher (recommended UX).
  path: `scripts/summon.ps1`
  example: `pwsh .\scripts\summon.ps1 -Task '...' -Online`
- `orchestrator`: Canonical multi-agent orchestrator (run-dir engine).
  path: `scripts/triad_orchestrator.ps1`
- `agent_runner`: Executes one agent seat; hybrid router (cloud/local) with guardrails.
  path: `scripts/agent_runner_v2.py`
- `skill_bridge`: Selects/injects external skills from ~/.codex and ~/.gemini.
  path: `scripts/skill_bridge.py`
- `manifest_router`: Writes state/manifest.json for machine-checkable budgets/plan.
  path: `scripts/manifest_router.py`
- `team_compiler`: Compiles a 3..7 role team for the prompt (reduces swarm chaos).
  path: `scripts/team_compiler.py`
- `agent_cards`: Writes state/agent_cards.json (A2A-style 'Agent Cards' for dynamic routing/team introspection).
  path: `scripts/agent_cards.py`
- `contract_repair`: Repairs missing DECISION_JSON by re-running only failing seats.
  path: `scripts/contract_repair.py`
- `patch_apply`: Applies ```diff blocks from best agent output with guardrails.
  path: `scripts/council_patch_apply.py`
- `verify`: Runs verification pipeline after patches (strict mode supported).
  path: `scripts/verify_pipeline.py`
- `bus`: Async council bus (propose/claim/ack decisions + hygiene sweep).
  path: `scripts/council_bus.py`
- `eval_harness`: Scores prior runs for contract compliance + failure signals.
  path: `scripts/eval_harness.py`
- `retrieval_pack`: Bounded multi-retriever pack (code/docs/memory) injected into prompts.
  path: `scripts/retrieval_pack.py`
- `approve_action`: Appends an approval record (HITL) to state/approvals.jsonl for a specific action_id.
  path: `scripts/approve_action.py`
- `killswitch`: Writes STOP flags to stop runs/agents.
  path: `scripts/killswitch.py`
- `a2a_receive`: Receives A2A payloads (stdin/file) and enqueues into ramshare/state/a2a/inbox with idempotency + ACK.
  path: `scripts/a2a_receive.py`
- `a2a_executor`: Processes ramshare/state/a2a/inbox and executes a2a.v2 action_payload (default-off; enable with GEMINI_OP_REMOTE_EXEC_ENABLE=1).
  path: `scripts/a2a_remote_executor.py`
- `a2a_bridge_wsl`: Routes A2A payloads into a local WSL distro via stdin (no SSH).
  path: `scripts/a2a_bridge_wsl.py`
- `health_reporter`: Runs health checks, parses results, and generates a structured Markdown report.
  path: `scripts/health_reporter.py`
  example: `python scripts/health_reporter.py --repo-root . --run-dir .`
- `finance_council_run`: Queues or runs the finance_council multi-agent skillset (technical/fundamental/sentiment/risk/execution).
  path: `scripts/finance_council_run.py`
  example: `python scripts/finance_council_run.py --account-id Z39213144 --run-now`
- `market_theme_run`: Queues or runs theme-driven stock research for any finance theme and returns ranked non-portfolio candidates.
  path: `scripts/market_theme_run.py`
  example: `python scripts/market_theme_run.py --theme \"best ai micro investments for this week\" --run-now`
- `rb_style_train`: Builds a reusable style profile from local artwork ZIP/folder for Redbubble product generation consistency.
  path: `scripts/rb_style_train.py`
  example: `python scripts/rb_style_train.py --zip \"C:\path\to\artwork.zip\"`
- `rb_style_cycle`: Runs multi-cycle style calibration + variety testing to tune generator overrides toward reference linework metrics.
  path: `scripts/rb_style_cycle.py`
  example: `python scripts/rb_style_cycle.py --cycles 8 --zip \"C:\path\to\artwork.zip\" --apply`
- `rb_catalog_scan`: Scans local + live Redbubble sources to build duplicate-prevention catalog cache.
  path: `scripts/rb_catalog_scan.py`
  example: `python scripts/rb_catalog_scan.py --shop-url \"https://www.redbubble.com/people/<handle>/shop?asc=u\"`
- `art_syndicate_run`: Runs the Art Syndicate council loop (trend hunter -> generator -> compliance/quality/SEO council -> packet).
  path: `scripts/art_syndicate_run.py`
  example: `python scripts/art_syndicate_run.py --query \"trendy spots in michigan 2026\"`
- `rb_photo_to_style`: Converts a real landmark/building photo into your Redbubble-ready line-art style with iterative scoring + preview output.
  path: `scripts/rb_photo_to_style.py`
  example: `python scripts/rb_photo_to_style.py --image \"C:\Users\codym\Downloads\Fox Theater.jpg\" --cycles 14`
