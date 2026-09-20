# /search-docs — library docs in THIS checkout (optional)

Usage: `/search-docs <query>`

Prefer `ramp-kit/conventions/rules.yaml` + the gate. MCP is stdio
`diffusers-docs` (Cloud dropdown: `diffusers-docs-mcp`). No Hub HTTP.

```bash
python3 ramp-kit/tools/docs_mcp_server.py --query $1
```

If `$1` is empty:

```bash
python3 ramp-kit/tools/docs_mcp_server.py --query "scheduler set_timesteps step SchedulerMixin register_to_config"
```

If the MCP tool `search_docs` is in your list, call that instead.
