# Remote Targets (What It Means)

In Gemini-OP, a "remote target" is simply the environment that actually runs `action_payload` work (tool calls) for A2A messages.

Examples:
- Local (this Windows machine): run `scripts/a2a_remote_executor.py` on Windows to process inbox jobs.
- WSL (recommended on this machine): run the executor inside Ubuntu WSL to simulate a Linux "server" without SSH or extra hardware.
- SSH host: run the executor on another machine over SSH.

## Recommended On This Machine (Windows + CPU-only)

Use WSL Ubuntu as the remote target:
1. Ensure Ubuntu exists: `wsl -l -v` should list `Ubuntu`.
2. Confirm `ramshare/state/a2a/peers.json` has a `wsl_ubuntu` peer with `"transport": "wsl"`.
3. Start the WSL executor:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start-a2a-executor-wsl.ps1
```

With the executor running, routing a v2 A2A payload to `--peer wsl_ubuntu` will enqueue into `ramshare/state/a2a/inbox`, then the WSL executor will execute it (only when `GEMINI_OP_REMOTE_EXEC_ENABLE=1` is set).

