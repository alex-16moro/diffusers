"""Conservative reviewer-text inventory; the complete patch remains authoritative."""

import ast
import io
import re
import tokenize

from .core import git, safe_path


def inventory(repo, task):
    entries = []
    for path in sorted(task["editable_files"]):
        diff = git(
            repo,
            "diff",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--no-renames",
            "--unified=0",
            task["base_sha"],
            "--",
            path,
        ).decode()
        added = set()
        line = 0
        for row in diff.splitlines():
            if row.startswith("@@ "):
                line = int(re.search(r"\+(\d+)", row).group(1))
            elif row.startswith("+") and not row.startswith("+++"):
                added.add(line)
                line += 1
            elif row.startswith(" "):
                line += 1
        if not added or not path.endswith(".py"):
            continue
        source = safe_path(repo, path).read_text()
        try:
            tree = ast.parse(source)
            docstrings = set()
            for node in ast.walk(tree):
                body = getattr(node, "body", None)
                if isinstance(body, list) and body and isinstance(body[0], ast.Expr):
                    value = body[0].value
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        docstrings.add(id(value))
            for node in ast.walk(tree):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if added.intersection(range(node.lineno, node.end_lineno + 1)):
                        entries.append(
                            {
                                "path": path,
                                "line": node.lineno,
                                "kind": "docstring"
                                if id(node) in docstrings
                                else "string literal (including errors and test text)",
                                "text": node.value,
                            }
                        )
            for tok in tokenize.generate_tokens(io.StringIO(source).readline):
                if tok.type == tokenize.COMMENT and tok.start[0] in added:
                    entries.append(
                        {"path": path, "line": tok.start[0], "kind": "comment", "text": tok.string}
                    )
        except (SyntaxError, tokenize.TokenError, IndentationError) as exc:
            entries.append({"path": path, "line": 1, "kind": "manual inspection required", "text": str(exc)})
    return sorted(entries, key=lambda e: (e["path"], e["line"], e["kind"]))


def markdown(entries, title):
    lines = [
        "## Exact wording awaiting human approval",
        "",
        "Approval: NOT_RUN. Read the complete contribution.patch as well as this conservative inventory.",
        "All added/changed Python string literals and comments are listed, including test text.",
        "Dynamically constructed text must also be checked in the patch; this is not a semantic completeness guarantee.",
        "",
        "Proposed commit message (draft):",
        "",
        "```text",
        title,
        "```",
        "",
        "The PR title and body above are also drafts awaiting exact-wording approval.",
    ]
    for entry in entries:
        lines += [
            "",
            f"### {entry['path']}:{entry['line']} — {entry['kind']}",
            "",
            "````text",
            entry["text"],
            "````",
        ]
    return "\n".join(lines) + "\n"
