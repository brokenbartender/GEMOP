# Permanent `ramshare` + SSH Sync

This keeps `C:\Gemini\ramshare` on this desktop synchronized to your laptop over SSH.

## Desktop (this machine)

1. Run setup once:
   `powershell -NoProfile -ExecutionPolicy Bypass -File C:\Gemini\scripts\setup-ssh-ramshare-permanent.ps1 -LaptopHost Gemini-laptop -LaptopAddress <LAPTOP_IP_OR_DNS> -LaptopUser <LAPTOP_USER> -RemoteRepoRoot ~/Gemini-op`
2. Confirm config file exists:
   `C:\Gemini\scripts\ramshare-sync.local.json`
3. Test one manual sync:
   `powershell -NoProfile -ExecutionPolicy Bypass -File C:\Gemini\scripts\sync-ramshare.ps1`
4. Check logs:
   `Get-Content C:\Gemini\logs\sync\ramshare-sync.log -Tail 50`

## Laptop (other computer)

1. Install and enable OpenSSH server.
2. Ensure `~/.ssh/authorized_keys` contains the desktop public key from:
   `C:\Users\codym\.ssh\id_ed25519.pub`
3. Ensure repo exists at `~/Gemini-op` (or match `remote_ramshare_root` in desktop config).
4. Verify login from desktop:
   `ssh Gemini-laptop echo ok`

## Scheduled task

The setup script registers task `GeminiRamshareSync`:
- Runs at logon.
- Repeats every 5 minutes.

Manage task:
- Check: `Get-ScheduledTask GeminiRamshareSync`
- Run now: `Start-ScheduledTask GeminiRamshareSync`
- Remove: `Unregister-ScheduledTask -TaskName GeminiRamshareSync -Confirm:$false`

## Notes

- `scripts/ramshare-sync.local.json` is ignored by git (machine-local secrets/host info).
- Included sync folders are controlled by `include_paths` in that local config.
