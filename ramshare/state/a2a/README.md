# A2A Peers

Create `peers.json` in this folder to enable remote A2A routing.

Example:

```json
{
  "laptop": {
    "host": "cody-laptop",
    "remote_repo": "~/gemini-op",
    "remote_python": "python3"
  }
}
```

Then route automatically:

```powershell
python C:\gemini\scripts\a2a_router.py --route auto --peer laptop --message "sync status"
```
