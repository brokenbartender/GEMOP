# Configs

This repo uses `configs/` for Gemini CLI configuration:

- `config.base.toml`: shared baseline (portable)
- `config.core.toml`: stronger defaults (portable)
- `config.full.toml`: default profile used by `start.ps1` (portable)
- `config.max.toml`: enables more MCP servers (portable)
- `config.local.toml`: local overrides (ignored; do not commit)
- `config.active.toml`: generated at runtime (ignored)

`start.ps1` assembles `config.active.toml` by concatenating:

1. `configs/config.base.toml`
2. `configs/config.<profile>.toml`
3. `configs/config.local.toml` (if present)

To customize trust rules and any machine-specific paths, edit `configs/config.local.toml`.

