# Gemini OP Progressive Plan (Living Doc)

This is the shared, editable running document for improving `brokenbartender/gemini-op`.

## North Star
- Optimize Gemini OP for fast startup + low-friction workflows.
- Keep “power” features (network, browser, repo mutation) available but controlled via profiles and gating.

## Current State (Facts)
- Repo: `C:\gemini` tracking `origin/main` (`https://github.com/brokenbartender/gemini-op.git`).
- Always-on daemons (when using `browser|research|full` profiles):
  - Memory: `http://localhost:3013/mcp`
  - Playwright MCP: `http://localhost:8931/mcp`
  - Semantic search MCP (research/full): `http://localhost:3014/mcp`

## Active Decisions
- Use profile TOMLs as the coarse-grained capability selector.
- Prefer always-on Streamable HTTP for heavy MCP servers to reduce session startup overhead.

## Resource Log (Append-Only)

### 2026-02-11
- “God-Mode Implementation Specification” (local file):
  - `C:\Users\codym\Downloads\Below is a concrete “God‑Mode Imple.txt`
  - Notes: generic governance spec; treat as inspiration, not implementation plan.
- AIMA (Artificial Intelligence: A Modern Approach) site:
  - `http://aima.cs.berkeley.edu/`
  - Angle to apply: define performance measures; add observability; prefer stateful, measurable control loops.
- Deep Learning Book:
  - `https://www.deeplearningbook.org/`
  - Angle to apply: (pending) extract concrete engineering improvements only if they map to measurable system behavior.
- Dive Into Deep Learning (D2L):
  - `https://d2l.ai/`
  - Angle to apply: treat “system performance” like an ML training loop:
    - Measure first (timers, counters, failure rates), then iterate.
    - Prefer batching/streaming and caching over repeated cold-start work.
    - Keep artifacts small and reusable (avoid reloading large schemas/tools on every run).
- Poole & Mackworth: Artificial Intelligence, Foundations of Computational Agents (3E):
  - `https://artint.info/3e/html/ArtInt3e.html`
  - Angle to apply (agent-engineering, not ML):
    - Hierarchical control: keep `profiles/` as top-level modes, but add smaller “sub-modes” inside a profile (e.g. `browser` but with browser-only vs browser+git).
    - Search/planning: treat common workflows as fixed plans (health -> reproduce -> change -> test -> push) and make them measurable.
    - Acting under uncertainty: explicit retries/backoff + circuit breakers (daemon health, network flakiness) instead of blind restart loops.
- Probabilistic Machine Learning (Murphy) Book 1:
  - `https://probml.github.io/pml-book/book1.html`
  - Angle to apply (uncertainty + calibration, operationalized):
    - Track reliability: model “tool call failure probability” per server/profile and use it to decide retries vs fallback.
    - Bayesian-ish health scoring: combine signals (port listening, last error, latency) into a single “daemon health” score that gates enabling heavy tools.
    - Use logging to estimate these probabilities over time (simple EWMA is fine).
- Understanding Machine Learning (Shalev-Shwartz & Ben-David):
  - `https://www.cs.huji.ac.il/~shais/UnderstandingMachineLearning/`
  - Angle to apply (generalization + evaluation discipline):
    - Define “train” vs “test” for ops changes: don’t tune profiles/daemons based only on one machine/run; keep a small held-out set of scenarios (cold start, network down, repo dirty, etc.).
    - Prefer simple models/heuristics with clear guarantees (timeouts, backoff, circuit breakers) over brittle, overfit rules.
    - Measure regressions: when changing profiles/scripts, record before/after metrics and keep the comparison in logs.
- Mathematics for Machine Learning (MML):
  - `https://mml-book.github.io/`
  - Angle to apply (systems hygiene via math basics):
    - Treat latency/throughput/cost as first-class “dimensions” and keep a single normalized score (weighted sum) so tradeoffs are explicit.
    - Use simple linear models for predictions (e.g., expected startup time = base + sum(server_startup)) before you reach for anything fancier.
    - Keep configuration composable: profiles should be additive/orthogonal where possible (avoid duplicated blocks drifting apart).
- Bishop (2006) Pattern Recognition and Machine Learning (PDF):
  - `https://www.microsoft.com/en-us/research/uploads/prod/2006/01/Bishop-Pattern-Recognition-and-Machine-Learning-2006.pdf`
  - Angle to apply (probabilistic reasoning for ops, kept simple):
    - Treat “daemon healthy” vs “unhealthy” as a latent variable inferred from signals (port open, error logs, response latency).
    - Use thresholded log-odds (or just weighted features) to decide when to enable/disable heavy MCP endpoints automatically.
    - Use priors: default to “unhealthy” after reboot until a successful check passes, to avoid optimistic startup flakiness.
- Neural Network (PDF mirror; unverified source):
  - `http://103.203.175.90:81/fdScript/RootOfEBooks/E%20Book%20collection%20-%202024%20-%20G/CSE%20%20IT%20AIDS%20ML/Neural%20Network.pdf`
  - Status: link recorded only (not downloaded/parsed yet). Prefer an official publisher/author URL before we rely on it.

## Improvement Backlog
- Implemented: health check script `scripts/health.ps1` (validates daemons + core deps per profile).
- Implemented: distillation runner `scripts/distill.ps1` (generates per-resource prompts; can optionally run `gemini exec`).
- TODO (A2A): enforce schema version on all outbound/inbound A2A payloads (`a2a.v1`) and reject invalid contracts.
- TODO (A2A): replace heuristic ACK detection with explicit ACK contract (`a2a.ack.v1`) in router + senders.
- TODO (A2A): stale lock and stale watchdog PID cleanup during health checks to avoid deadlock-on-start.
- TODO (A2A): add dispatcher replay helper for single `task_id` postmortem recovery.
- TODO (Free-only): add a hard preflight/governance gate that blocks paid providers/endpoints in all autonomous profiles.
- Add a single health check command/script that validates:
  - profile currently active
  - daemon ports listening (when required)
  - MCP endpoints reachable
- Add structured logs for startup + daemon status.
- Add a general MCP “gateway/proxy” server (policy + allowlists) to enforce tool gating (future).
- Add a security baseline: OWASP-driven controls + secrets management + audit logging.
- Add an ingestion pipeline: refresh resources -> extract text -> index -> generate agent task stubs -> distill into committed notes.

## Next Step
- Fill in the “performance measures” we care about (startup time, tool-call latency, failures) and wire in logging/health checks.
- Run `scripts/ingest-and-index.ps1 -Profile research` after adding resources, then distill the agent task stubs into `ramshare/notes/distilled/` and fold only the final decisions into this doc.
  - Prepare prompts: `scripts/distill.ps1 -Profile research -Mode prepare`
  - (Optional) Run non-interactively: `scripts/distill.ps1 -Profile research -Mode run`

## Security Plan (Incorporated)

### Threat Model (Gemini OP)
- Assets: repo contents, credentials/tokens (GitHub, Notion, etc.), local filesystem, logs, any documents ingested by MCPs.
- Trust boundaries: Gemini CLI <-> MCP servers (stdio/HTTP), local daemons (ports), external HTTP APIs.
- Primary risks: prompt injection causing dangerous tool use, secret leakage via logs/prompts, supply-chain attacks via `npx` installs, over-broad permissions, and weak auditing.

### Security Baseline Controls (Priority-Ordered)
P0 (must-have)
- Least privilege per profile/server: enable only required MCP servers/tools for the current profile; separate tokens by capability (read vs write).
- Secrets policy: no secrets in TOML/scripts/logs; only via vault/env vars; rotate/revoke; redact in logs.
- Tool gating: allowlist high-risk commands (shell/git) and block dangerous patterns; never execute raw model/user strings without policy checks.
- Supply-chain pinning: prefer globally installed/pinned servers over ad-hoc `npx -y`; keep versions explicit where feasible.
- Tamper-evident audit trail: log profile switches, daemon start/stop, tool invocations (tool name, args hash, duration, exit code), and redacted errors.

P1 (next)
- Budget and rate limits: cap retries and tool-call volume; circuit breakers on repeated failures.
- Data redaction: strip secrets/PII from prompts and stored artifacts; avoid persisting sensitive content in long-lived logs.
- Harden exposed ports: bind daemons to loopback only; document ports and expected endpoints; verify reachability before enabling a URL-backed MCP.

P2 (hardening)
- Integrity checks: checksums for downloaded binaries/artifacts; CI to validate config drift and deny unreviewed changes to security-sensitive files.
- Documentation: keep a living `security.md` with threat model, secrets handling, and break-glass steps.

### Security Resources (Links)
- OWASP Top 10 / 2025 / LLM / CI-CD / Client-side / Mobile / ML Security Top 10
- OWASP Secrets Management Cheat Sheet
- Ross Anderson Security Engineering (3E)
- NIST SP 800-204 (Microservices Security)
- NIST SP 800-207 (Zero Trust Architecture): PDP/PEP model for Tool Gateway enforcement
- NIST SP 800-162 (ABAC): attribute-based policies for action-level tiers
- Google: Building Secure and Reliable Systems (Least Privilege, Auditing, MPA patterns)
- Google Zanzibar (ReBAC): fine-grained permission modeling for “who can do what”
- OPA (Rego) + Oso Academy: policy-as-code implementation approaches
- BeyondCorp papers: context-aware access beyond perimeter
- NIST SP 800-53r5 AU controls: audit/accountability requirements
- Google SRE book: simplicity + emergency response (“break-glass”)
- Microsoft Cloud Design Patterns: circuit breaker + throttling patterns (tool short-circuiting)
- Feature Toggles: ops toggles for kill switches (file/env var flags)
- AWS Well-Architected (Reliability): bulkheads, fault isolation, graceful degradation
- FinOps Framework: automated budget controls and spend anomaly response
- Chaos engineering: routinely test kill switches and failure modes
- Patterns of Distributed Systems: heartbeat + leases for remote control signals
- NIST SP 800-61r2: incident handling phases (containment/eradication/recovery)
- NIST SP 800-190: container security guide (non-root, least privilege, read-only FS)
- NVIDIA: sandboxing agentic workflows (MCP-specific execution risk guidance)
- gVisor architecture: stronger isolation than vanilla containers (userspace kernel)
- Firecracker paper: microVM isolation patterns (hard boundaries)
- Docker security docs: seccomp, dropped caps, read-only rootfs guidance
- K8s Pod Security Standards: “restricted” checklist as a hardening baseline
- 12-factor app: stateless processes and disposability principles for safer automation
- OSTEP: OS fundamentals underpinning timeouts/protection (for enforcing safe execution)

## Recursive Self-Improvement Controls (Incorporated)

### Principles (What We Enforce)
- Separation of duties: Proposer != Auditor != Executor.
- Governance is write-protected: policy files and security-critical configs require explicit Tier-5 human unlock.
- Mandatory evidence: every patch needs a diff, test evidence, and rollback steps before merge/deploy.
- Off-switch/kill switch is always available and can’t be overridden by the agent.

### Practical Controls (Gemini OP)
P0
- “Propose-only” mode by default: agent can prepare diffs + run tests, but cannot push/merge without human approval.
- Auditor step required: a second pass that reviews diffs against policy (secrets, allowlists, destructive actions).
- Protect governance files by repo policy: keep them in a dedicated folder and treat changes as high-risk (require manual review).

P1
- Add structured “hazard analysis” + rollback section to change requests (STPA-inspired).
- Maintain a small “lessons learned” log to avoid repeating failures (reflection buffer).

### Resources (Links)
- Constitutional AI (critique/revise with a constitution): `https://arxiv.org/abs/2212.08073`
- Human Compatible (off-switch / control framing): `https://www.penguinrandomhouse.com/books/566677/human-compatible-by-stuart-russell/`
- Engineering a Safer World (STPA, hazard analysis): `https://direct.mit.edu/books/oa-monograph/2908/engineering-a-safer-world`
- Reflexion (reflection loop): `https://arxiv.org/abs/2303.11366`
- AI Safety book (modern safety frameworks): `https://www.aisafetybook.com/`
- Google SRE (release engineering): `https://sre.google/sre-book/release-engineering/`
- Continuous Delivery (deployment pipeline): `https://continuousdelivery.com/`
