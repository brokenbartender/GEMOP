# Human-in-the-Loop Protocol

This document outlines the protocol for Human-in-the-Loop (HITL) interventions within the `gemini-op-clean` agent ecosystem. HITL mechanisms ensure that critical decisions, high-risk operations, or uncertain outcomes are reviewed and approved by a human operator, enhancing safety, compliance, and reliability.

## Purpose

- **Safety**: Prevent agents from executing harmful, irreversible, or unintended actions.
- **Compliance**: Ensure adherence to legal, ethical, and organizational policies.
- **Quality Assurance**: Provide human oversight for complex or ambiguous tasks where agent confidence is low.
- **Learning**: Allow human feedback to inform and refine agent behavior over time.

## Triggers for Human-in-the-Loop

Agents should identify and trigger HITL when:

1.  A proposed action carries significant risk (e.g., as determined by `scripts/gemini_a2a_send_structured.py`'s `risk_score`).
2.  The agent's confidence in a decision is below a predefined threshold.
3.  An action involves modifying sensitive system components or external services.
4.  Explicit human approval is required by policy or prior instruction.

## Workflow for Human Approval

1.  **Agent Identifies HITL Need**: The agent determines that human intervention is required.
2.  **Payload Generation**: The agent prepares a clear, concise payload describing the proposed action, its context, potential risks, and required decision. This payload is typically sent to a console or a notification system.
3.  **Human Review**: A human operator reviews the payload.
4.  **Approval/Rejection**: The human operator either approves the action (e.g., using `scripts/approve_action.py`) or rejects it, potentially providing feedback or alternative instructions.
5.  **Agent Action**: If approved, the agent proceeds with the action. If rejected, the agent re-evaluates or terminates the task as per its internal policies.

