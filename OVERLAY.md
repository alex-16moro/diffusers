# Ramp Kit overlay (customer convention-as-code)

This checkout is a **fork of huggingface/diffusers**. The overlay lives in a
separate repo: [alex-16moro/diffuser_agent](https://github.com/alex-16moro/diffuser_agent).

Cloud Agent install clones it to `ramp-kit/` (gitignored). Do not edit
upstream `AGENTS.md` / `.ai/` — those stay Hugging Face's.

## Demo (Cloud Agent)

1. Launch on **this repo** (`alex-16moro/diffusers`), branch `main`.
2. Optional Hub MCP (HTTP, works on Cloud):

```json
{
  "mcpServers": {
    "huggingface": {
      "url": "https://huggingface.co/mcp"
    }
  }
}
```

3. Optional library-docs stdio (same VM; no OAuth):

```json
{
  "mcpServers": {
    "diffusers-docs": {
      "type": "stdio",
      "command": "python3",
      "args": ["-u", "/workspace/.cursor/mcp-diffusers-docs.py"]
    }
  }
}
```

4. Scaffold writes `src/diffusers/schedulers/scheduling_euler_lite.py` **in this
   library**. Gate: `python3 ramp-kit/tools/convention_check.py <that file>`.
5. Open the PR **on this fork**, not on huggingface/diffusers.

Docs search uses `docs/source/en` in this checkout (real library docs).
The catch-early fixture is `ramp-kit/examples/candidate_scheduler` — do not copy it.
