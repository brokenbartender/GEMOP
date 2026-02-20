# 🌐 Gemini OP: System Architecture Document (2026 Edition)

This document provides a comprehensive mapping of the **Gemini OP Multi-Agent System (MAS)** across five critical dimensions: Topology, Agent Logic, State/Memory, Security, and Validation.

---

## 1. Topology & Routing (The Quorum)
The system employs a **Heterogeneous Trophic Architecture**, moving away from flat chatrooms to a tiered, high-efficiency routing model.

- **Inter-Agent Communication**: Facilitated by the `council_bus.py` (decentralized message bus). Agents use **JSON Schema Enforcement** (`DECISION_JSON`) and **Digital Pheromones** (Quorum Sensing) to signal state shifts without central management.
- **Tiers & Escalation (Energy Tiers)**:
    - **EDGE**: Local `phi4:latest`. Handles micro-tasks (regex, parsing, syntax). Zero token cost.
    - **FLASH**: `gemini-2.0-flash`. Handles routine investigation, documentation, and summarization.
    - **PRO**: `gemini-2.0-flash`. The default "Workhorse" for coding and reasoning.
    - **ULTRA**: `gemini-2.0-pro-exp-02-05` / `o3-mini`. Activated for architecture, security audits, and complex root-cause analysis. Uses **Tree of Thoughts (ToT)** reasoning.
- **Speculative Routing**: `agent_runner_v2.py` includes a **Speculator** (Flash model) that "guesses" actions before the primary model acts, pre-warming the execution pipeline.

---

## 2. Agent Definitions
The swarm is comprised of specialized roles with autonomous triggers and designated toolkits.

| Role | Core Mission | Autonomous Trigger (Observer) | Key Tools |
| :--- | :--- | :--- | :--- |
| **Architect** | Process Reimagination | IDE focus on core modules | `repo_index.py`, `state_rebuilder.py` |
| **Engineer** | Recursive Implementation | File edits in `scripts/` | `agent_runner_v2.py`, `verify_pipeline.py` |
| **RedTeam** | Adversarial Simulation | High-stakes security tasks | Logic exploitation, Injection testing |
| **Operator** | End-to-End Action (LAM) | Data detected in `inbox/` | `council_patch_apply.py`, A2A Bridges |
| **Auditor** | Governance & Compliance | Kinetic patches detected | `formal_verifier.py`, `wampum_ledger.py` |
| **Observer** | Anticipatory Computing | File system modifications | `observer_daemon.py`, `real_time_context.json` |
| **Meta-Agent** | Self-Evolving Logic | Repeating failure patterns | `recursive_meta_agent.py`, `adaptive_policy.json` |

---

## 3. State & Memory (The Mycelium)
Memory is decentralized and multi-layered, preventing the "State Synchronization Nightmare."

- **Multi-Layered Memory Architecture**: `memory_manager.py` maintains three distinct ChromaDB collections:
    - **User Layer**: Past interactions for alignment.
    - **Project Layer**: Documentation indexed by the `ai_data_factory.py`.
    - **Agent Layer**: Governance logs and procedural lessons.
- **Memory Consolidation (MEM1)**: Instead of long logs, the `mem1_consolidator.py` synthesizes round outputs into a compact `<INTERNAL_STATE>` block, which is injected into every prompt.
- **State Recovery**: If an agent fails, the `triad_orchestrator.ps1` uses **Backtracking Logic** to revert the round counter and retry with fresh context from the MEM1 layer.

---

## 4. Security & Entropy (Dark Matter)
The system operates under a **Zero-Trust Agent Architecture**.

- **Neuro-Symbolic Safety Interlock**: `formal_verifier.py` mathematically proves code safety via AST analysis before `council_patch_apply.py` can touch the disk.
- **Immune System (Quorum Sensing)**: Agents check for `security_trip` pheromones on the bus before every turn. If a quorum is reached, the system performs an **Autonomous Hard Abort**.
- **Governance Logging**: Every agent decision is timestamped and recorded with full lineage metadata in the `agent_history` layer for "Ante-hoc" interpretability.
- **Self-Correction**: Agents feature a 1-turn **Recursive Self-Heal** loop to fix malformed JSON or missing contract blocks autonomously.

---

## 5. Validation & Testing
The system is verified through **Multi-Dimensional QA**.

- **System Testing**: `system_qa_check.py` automates functional integration (Memory), security (Verifier), and performance (Latency) checks.
- **Chaos Testing**: `chaos_monkey.py` intentionally starves local slots or corrupts manifests to test the system's autonomous resilience.
- **Usability Modeling**: `docs/usability_scenarios.md` provides goal-oriented task models (e.g., "Memory Integrity Audit") to measure human-AI alignment.
- **Value Realization (ROI)**: `ai_ops_report.py` tracks estimated human minutes saved and productivity multipliers (e.g., "45x vs Manual").

---
**Status**: System is **HEALTHY** and operating at **OMNI-GOD** level capabilities.
**Last Audit**: 2026-02-20
