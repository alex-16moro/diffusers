---
name: search-docs
description: Ground in this diffusers checkout's docs (docs/source/en) via the overlay MCP/CLI. Use before scaffolding when search_docs is missing.
---

# Search this library's docs

```bash
python3 ramp-kit/tools/docs_mcp_server.py --query "<the question>"
```

Cite provenance (`diffusers checkout` vs bundled snapshot). Prefer reading
`src/diffusers/schedulers/scheduling_euler_discrete.py` when the contract is
the question. `ramp-kit/conventions/rules.yaml` is the gate.
