# /search-docs — library docs in THIS checkout

Usage: `/search-docs <query>`

```bash
python3 ramp-kit/tools/docs_mcp_server.py --query $1
```

If `$1` is empty:

```bash
python3 ramp-kit/tools/docs_mcp_server.py --query "scheduler set_timesteps step SchedulerMixin register_to_config"
```

Provenance should say `diffusers checkout`, not `bundled snapshot`. If the
MCP tool `search_docs` is in your list, call that instead.

If snippets miss the contract, read `src/diffusers/schedulers/scheduling_euler_discrete.py`
and `ramp-kit/conventions/rules.yaml`.
