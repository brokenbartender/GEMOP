# Power Profile Recommendations

This document outlines recommended configurations ("knobs") for agent operations, tailored for different agent counts, and describes the killswitch/stop flow mechanism.

## Configuration Knobs by Agent Count

| Agent Count | CloudSeats | MaxLocalConcurrency | LocalSlotTimeout (s) | OllamaTimeout (s) |
|-------------|------------|---------------------|----------------------|-------------------|
| 3 Agents    | 1          | 2                   | 300                  | 120               |
| 5 Agents    | 2          | 3                   | 450                  | 180               |
| 12 Agents   | 4          | 6                   | 600                  | 240               |

*Note: These are baseline recommendations. Actual performance may vary based on task complexity and available resources. MaxLocalConcurrency should not exceed CloudSeats if cloud resources are primary.*

## Killswitch / Stop Flow

A killswitch mechanism allows for immediate termination of all active agent jobs.

### Mechanism:
The recommended killswitch involves terminating the primary agent orchestrator process. This ensures that all child processes and associated agent instances are gracefully (or forcefully, if necessary) shut down.

1.  **Identify Orchestrator Process**: Locate the process ID (PID) of the main agent orchestration service (e.g., `agent-orchestrator.exe` or `python agent_runner.py`).
2.  **Terminate Process**: Use system-level commands to terminate the process.
    *   **Windows (PowerShell)**: `Stop-Process -Id <PID> -Force`
    *   **Linux/macOS (Bash)**: `kill <PID>` or `kill -9 <PID>` for forceful termination.
3.  **Validation**: Confirm no agent processes are still running.

### Impact:
-   All in-progress agent tasks will be halted.
-   Unsaved work may be lost, depending on the agent's internal state management.
-   Logs and output artifacts up to the point of termination should still be accessible.

### Best Practice:
Implement automated monitoring for agent health and a mechanism for controlled shutdown before resorting to the killswitch.
