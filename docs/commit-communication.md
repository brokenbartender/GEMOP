# Commit Communication Workflow

Use these scripts to keep cross-machine requests consistent in every commit.

## 1) Ask for required machine info

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <REPO_ROOT>\scripts\request-other-computer-info.ps1 -TargetLabel laptop -RepoPathHint "<REPO_ROOT>"
```

## 2) Create a structured commit message automatically

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File <REPO_ROOT>\scripts\commit-with-communication.ps1 `
  -Type docs `
  -Summary "request laptop diagnostics for ssh sync" `
  -Context @("Need verified laptop network and ssh data to complete server/workstation sync") `
  -OtherComputer @("Run scripts/request-other-computer-info.ps1 commands on laptop", "Paste exact output in chat")
```

The generated commit includes:
- `Context`
- `Other-Computer`
- `Need-From-Other-Computer`
- `Validation`
