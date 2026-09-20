---
name: search-docs
description: Optional docs CLI for this diffusers checkout. Prefer AGENTS.md, .ai/, and the gate. Default mcp.json has no servers.
---

# Search this library's docs

```bash
python3 ramp-kit/tools/docs_mcp_server.py --query "<the question>"
```

Cite provenance (`diffusers checkout` vs bundled snapshot).
`ramp-kit/conventions/rules.yaml` is the gate. Root `AGENTS.md` and `.ai/`
are the library guide. Default `.cursor/mcp.json` has no servers.
