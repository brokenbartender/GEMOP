# Agents (V2)

This folder defines the declarative multi-agent system:

- `agents/roles/`: role templates (Markdown)
- `agents/packs/`: pack definitions (JSON)
- `agents/templates/`: shared header/footer snippets (Markdown)
- `agents/schemas/`: optional output schemas (JSON Schema)

Generation:
- Use `python scripts/agent_pack_generate.py` to generate an orchestrator-compatible run directory under `.agent-jobs/`.

Design principles:
- Roles are reusable; packs are ordered compositions.
- Canonical outputs are files in-repo (no hidden state).
- No consumer AI UI automation. Use APIs/local tools only.
- Avoid fragile PowerShell multiline payloads; pack init scripts should be thin wrappers around the generator.
