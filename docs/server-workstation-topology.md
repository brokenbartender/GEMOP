# Desktop Server + Laptop Workstation Topology

Goal:
- Desktop runs always-on services and is source-of-truth (`server`).
- Laptop is daily driver (`workstation`) and pulls shared state from server.

## Roles

- Server (desktop):
  - repo at `C:\Gemini`
  - pushes `ramshare` over SSH (optional)
  - runs daemons/watchdog/automation
- Workstation (laptop):
  - repo at `C:\Users\codym\Gemini-op`
  - pulls `ramshare` from server every 5 minutes
  - interactive coding and Gemini sessions

## 1) Server Setup (desktop)

Run on desktop:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Gemini\scripts\setup-ssh-ramshare-permanent.ps1 -LaptopHost Gemini-laptop -LaptopAddress <LAPTOP_IP> -LaptopUser codym -RemoteRepoRoot ~/Gemini-op
```

Manual test:

```powershell
ssh Gemini-laptop hostname
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Gemini\scripts\sync-ramshare.ps1
```

Expected:
- `ssh Gemini-laptop hostname` returns laptop hostname (not `CODYDESKTOP`).
- sync log includes `ramshare sync complete`.

## 2) Workstation Setup (laptop)

Copy scripts to laptop repo (already in git), then run on laptop:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup-laptop-workstation.ps1 -ServerHost Gemini-server -ServerAddress <DESKTOP_IP> -ServerUser codym
```

Manual pull test:

```powershell
ssh Gemini-server hostname
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\pull-ramshare-from-server.ps1 -ServerHost Gemini-server -LocalRamshareRoot "$HOME\Gemini-op\ramshare"
```

Expected:
- `ssh Gemini-server hostname` returns desktop hostname.
- pull log shows `ramshare pull complete`.

## 3) Recommended SSH aliases

Desktop (`~/.ssh/config`):

```sshconfig
Host Gemini-laptop
    HostName <LAPTOP_IP>
    User codym
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
```

Laptop (`~/.ssh/config`):

```sshconfig
Host Gemini-server
    HostName <DESKTOP_IP>
    User codym
    Port 22
    IdentityFile ~/.ssh/id_ed25519
    IdentitiesOnly yes
    StrictHostKeyChecking accept-new
```

## 4) Troubleshooting

- Self-sync blocked:
  - message: `resolves to local host (CODYDESKTOP)`
  - fix alias HostName to the real other machine IP.
- SSH key auth fails:
  - ensure desktop key is in laptop `~/.ssh/authorized_keys`
  - ensure laptop key is in desktop `~/.ssh/authorized_keys` for pull direction.
- Scheduled tasks:
  - server task: `GeminiRamshareSync`
  - laptop task: `GeminiRamsharePull`

## 5) Standardize Folder Organization (Both Machines)

Run this on each machine after pulling latest:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\optimize-workspace-layout.ps1 -RepoRoot C:\Gemini
```

For laptop repo path:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\optimize-workspace-layout.ps1 -RepoRoot C:\Users\codym\Gemini-op
```

This normalizes:
- `logs\sync\` for sync logs
- `state\locks\` for runtime locks
- `ramshare\evidence\{inbox,processed,rejected,staging,drafts,posted}`
- migration of legacy paths (`logs\ramshare-sync.log`, `state\ramshare-sync.lock`)

## 6) Fast Fix For `Gemini-laptop -> CODYDESKTOP`

If desktop resolves `Gemini-laptop` to itself, run this on desktop with your real laptop IP:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Gemini\scripts\setup-ssh-ramshare-permanent.ps1 -LaptopHost Gemini-laptop -LaptopAddress <REAL_LAPTOP_IP> -LaptopUser codym -RemoteRepoRoot ~/Gemini-op
```

Then verify:

```powershell
ssh -o BatchMode=yes -o ConnectTimeout=8 -o ConnectionAttempts=1 Gemini-laptop hostname
```

Expected:
- hostname is laptop name (not `CODYDESKTOP`).

Finally test sync:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File C:\Gemini\scripts\sync-ramshare.ps1
```
