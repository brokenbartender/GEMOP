# A2A Peers

Create `peers.json` in this folder to enable remote A2A routing.

Example:

```json
{
  "laptop": {
    "host": "cody-laptop",
    "transport": "ssh",
    "remote_repo": "~/gemini-op",
    "remote_python": "python3"
  }
}
```

Then route automatically:

```powershell
python C:\gemini\scripts\a2a_router.py --route auto --peer laptop --message "sync status"
```

## a2a.v2 (RPC / execution payloads)

For RPC-style execution, send `intent` + `action_payload` (schema `a2a.v2`). These are delivered via `scripts/a2a_receive.py` into the inbox and executed by `scripts/a2a_remote_executor.py` (default-off).

Enable execution explicitly:

```powershell
$env:GEMINI_OP_REMOTE_EXEC_ENABLE = "1"
python .\scripts\a2a_remote_executor.py
```

## WSL As A "Remote" Target (No SSH)

If you have a local WSL distro, you can use transport `wsl` to route payloads into it without networking:

```json
{
  "wsl_ubuntu": {
    "transport": "wsl",
    "distro": "Ubuntu",
    "remote_repo": "/home/<user>/gemini-op-clean",
    "remote_python": "python3",
    "platform": "linux"
  }
}
```
