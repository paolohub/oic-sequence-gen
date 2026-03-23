"""
generators/mermaid.py — Render a parsed sequence as a Mermaid Markdown (.md) string.
"""

from __future__ import annotations

from oic_sequence_gen.parser import IARParser


def generate_mermaid(parser: IARParser) -> str:
    """Return a Markdown document containing a Mermaid sequenceDiagram block."""
    lines: list[str] = [
        f"# Sequence Diagram — {parser.project_code}",
        "",
        "```mermaid",
        "sequenceDiagram",
        "    autonumber",
        "",
    ]
    for alias, kind, label in parser.participants:
        lines.append(f"    {kind} {alias} as {label}")
    lines.append("")

    depth = 1

    def ind() -> str:
        return "    " * depth

    for step in parser.sequence:
        t = step["type"]

        if t == "invoke":
            frm = step["from"]
            to  = step["to"]
            msg = step["msg"]
            ret = step.get("ret", "")
            lines.append(f"{ind()}{frm}->>{to}: {msg}")
            if ret:
                lines.append(f"{ind()}{to}-->>{frm}: {ret}")

        elif t == "internal":
            a   = step["actor"]
            msg = step["msg"]
            lines.append(f"{ind()}{a}->>{a}: {msg}")

        elif t == "throw":
            frm = step["from"]
            to  = step["to"]
            msg = step["msg"]
            lines.append(f"{ind()}{frm}-->>{to}: THROW {msg}")

        elif t == "response":
            frm = step["from"]
            to  = step["to"]
            msg = step["msg"]
            lines.append(f"{ind()}{frm}-->>{to}: {msg}")

        elif t == "loop_start":
            lines.append(f"{ind()}loop {step['label']}")
            depth += 1

        elif t == "loop_end":
            depth = max(1, depth - 1)
            lines.append(f"{ind()}end")

        elif t == "alt_branch":
            kw   = step["kw"]
            cond = step["cond"]
            if kw == "alt":
                lines.append(f"{ind()}alt {cond}")
                depth += 1
            else:
                depth = max(1, depth - 1)
                lines.append(f"{ind()}else {cond}")
                depth += 1

        elif t == "alt_end":
            depth = max(1, depth - 1)
            lines.append(f"{ind()}end")

        elif t == "par_start":
            lines.append(f"{ind()}par {step['label']}")
            depth += 1

        elif t == "par_branch":
            depth = max(1, depth - 1)
            lines.append(f"{ind()}and {step['label']}")
            depth += 1

        elif t == "par_end":
            depth = max(1, depth - 1)
            lines.append(f"{ind()}end")

        elif t == "group_start":
            lines.append(f"{ind()}rect rgb(255, 245, 220)")
            lines.append(f"{ind()}    Note over OIC: {step['label']}")
            depth += 1

        elif t == "group_end":
            depth = max(1, depth - 1)
            lines.append(f"{ind()}end")

        elif t == "section":
            lines.append("")

        elif t == "note":
            text = step["text"].replace("\n", " ")
            lines.append(f"{ind()}Note over OIC,Client: {text}")

    lines.append("```")
    return "\n".join(lines)
