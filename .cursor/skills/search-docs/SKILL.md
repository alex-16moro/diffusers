---
name: search-docs
description: Optional docs CLI for this diffusers checkout. Prefer the gate; MCP is stdio search_docs.
---

# Search this library's docs

```bash
python3 ramp-kit/tools/docs_mcp_server.py --query "<the question>"
```

Cite provenance (`diffusers checkout` vs bundled snapshot).
`ramp-kit/conventions/rules.yaml` is the gate.
`.cursor/mcp.json` is stdio `diffusers-docs` only (no Hub HTTP).
Cloud dropdown: `diffusers-docs-mcp`.
