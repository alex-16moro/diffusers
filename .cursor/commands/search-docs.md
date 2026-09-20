# /search-docs — optional keyword search of THIS checkout's docs

Usage: `/search-docs <query>`

Prefer `ramp-kit/conventions/rules.yaml`, root `AGENTS.md`, `.ai/`, and the
reference source those files name. Default `.cursor/mcp.json` has no servers.

```bash
python3 ramp-kit/tools/docs_mcp_server.py --query $1
```

If `$1` is empty:

```bash
python3 ramp-kit/tools/docs_mcp_server.py --query "scheduler set_timesteps step SchedulerMixin register_to_config"
```
