# Gemini Swarm IPC

## Communication Standard

All agents MUST write their current state to `.gemini/ipc/[name].status`.

### States
- `STARTING`
- `WORKING`
- `WAITING_FOR_INPUT`
- `DONE`
- `ERROR`

The Manager is the only agent permitted to read other agents' logs. Status files are the canonical signal for when to poll those logs.
