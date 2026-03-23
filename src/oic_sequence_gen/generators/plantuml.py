"""
generators/plantuml.py — Render a parsed sequence as a PlantUML (.puml) string.
Also exposes _encode_plantuml() used by the PNG generator for the web-server fallback.
"""

from __future__ import annotations

import zlib

from oic_sequence_gen.constants import PUML_ALPHABET
from oic_sequence_gen.parser import IARParser

# ── PlantUML web-server encoding ───────────────────────────────────────────────

def _encode_plantuml(text: str) -> str:
    """
    Encode a PlantUML source string for use with the PlantUML web server API.
    The encoding is: UTF-8 → zlib deflate → custom base-64 alphabet.
    """
    data = zlib.compress(text.encode("utf-8"))

    def _enc3(b1: int, b2: int, b3: int) -> str:
        return (
            PUML_ALPHABET[(b1 >> 2) & 0x3F]
            + PUML_ALPHABET[((b1 & 0x3) << 4) | ((b2 >> 4) & 0xF)]
            + PUML_ALPHABET[((b2 & 0xF) << 2) | ((b3 >> 6) & 0x3)]
            + PUML_ALPHABET[b3 & 0x3F]
        )

    result = ""
    for i in range(0, len(data) - 2, 3):
        result += _enc3(data[i], data[i + 1], data[i + 2])
    rem = len(data) % 3
    if rem == 1:
        result += _enc3(data[-1], 0, 0)[:2]
    elif rem == 2:
        result += _enc3(data[-2], data[-1], 0)[:3]
    return result


# ── PlantUML generator ─────────────────────────────────────────────────────────

def generate_puml(parser: IARParser) -> str:
    """Return the complete PlantUML source for the integration sequence diagram."""
    lines: list[str] = [
        f"@startuml {parser.project_code}",
        "",
        f"title {parser.project_code}\\n{parser.project_name} — Sequence Diagram",
        "",
        "skinparam sequenceMessageAlign center",
        "skinparam responseMessageBelowArrow true",
        "skinparam maxMessageSize 200",
        "skinparam BoxPadding 10",
        "skinparam ParticipantPadding 20",
        "",
        "skinparam participant {",
        "    BackgroundColor #DDEEFF",
        "    BorderColor #336699",
        "    FontStyle bold",
        "}",
        "skinparam actor {",
        "    BackgroundColor #FFFFCC",
        "    BorderColor #999900",
        "}",
        "skinparam note {",
        "    BackgroundColor #FFFACD",
        "    BorderColor #CCAA00",
        "}",
        "",
    ]

    for alias, kind, label in parser.participants:
        lines.append(f"{kind:<12}{alias:<14}as \"{label}\"")
    lines.append("")

    depth = 0

    def ind() -> str:
        return "    " * depth

    for step in parser.sequence:
        t = step["type"]

        if t == "invoke":
            frm        = step["from"]
            to         = step["to"]
            msg        = step["msg"]
            ret        = step.get("ret", "")
            is_trigger = step.get("is_trigger", False)

            if is_trigger:
                lines.append(f"{ind()}{frm}         ->  {to}         : {msg}")
                lines.append(f"{ind()}activate {to}")
            else:
                lines.append(f"{ind()}{frm}         ->  {to}         : {msg}")
                if to not in ("OIC", "Client"):
                    lines.append(f"{ind()}activate {to}")
                if ret:
                    lines.append(f"{ind()}{to}         --> {frm}         : {ret}")
                if to not in ("OIC", "Client"):
                    lines.append(f"{ind()}deactivate {to}")

        elif t == "internal":
            a   = step["actor"]
            msg = step["msg"]
            lines.append(f"{ind()}{a}         ->  {a}         : {msg}")

        elif t == "throw":
            frm = step["from"]
            to  = step["to"]
            msg = step["msg"]
            lines.append(f"{ind()}{frm}         -[#red]-> {to}      : **THROW** {msg}")

        elif t == "response":
            frm = step["from"]
            to  = step["to"]
            msg = step["msg"]
            lines.append(f"{ind()}{frm}         --> {to}         : {msg}")
            lines.append(f"{ind()}deactivate {frm}")

        elif t == "loop_start":
            lines.append(f"{ind()}loop {step['label']}")
            depth += 1

        elif t == "loop_end":
            depth = max(0, depth - 1)
            lines.append(f"{ind()}end")

        elif t == "alt_branch":
            kw   = step["kw"]
            cond = step["cond"]
            if kw == "alt":
                lines.append(f"{ind()}alt {cond}")
                depth += 1
            else:
                depth = max(0, depth - 1)
                lines.append(f"{ind()}else {cond}")
                depth += 1

        elif t == "alt_end":
            depth = max(0, depth - 1)
            lines.append(f"{ind()}end")

        elif t == "par_start":
            lines.append(f"{ind()}par {step['label']}")
            depth += 1

        elif t == "par_branch":
            depth = max(0, depth - 1)
            lines.append(f"{ind()}else {step['label']}")
            depth += 1

        elif t == "par_end":
            depth = max(0, depth - 1)
            lines.append(f"{ind()}end")

        elif t == "group_start":
            lines.append(f"{ind()}group {step['label']}")
            depth += 1

        elif t == "group_end":
            depth = max(0, depth - 1)
            lines.append(f"{ind()}end")

        elif t == "section":
            lines.append("")
            lines.append(f"== {step['title']} ==")
            lines.append("")

        elif t == "note":
            lines.append(f"{ind()}note over OIC, Client #FFD0D0")
            for ln in step["text"].splitlines():
                lines.append(f"{ind()}    {ln}")
            lines.append(f"{ind()}end note")

    lines.append("@enduml")
    return "\n".join(lines)
