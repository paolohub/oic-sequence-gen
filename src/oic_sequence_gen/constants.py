"""
constants.py — Invariant constants for oic-sequence-gen.

Only values fixed by the OIC platform schema belong here.
All integration-specific data (participants, route conditions, return labels)
is derived dynamically by IARParser from the archive contents.
"""

# ── XML Namespaces ─────────────────────────────────────────────────────────────
# Defined by Oracle's OIC platform schema; identical across all integrations.
NS_FLOW = "http://www.oracle.com/2014/03/ics/flow/definition"
NS_PROJ = "http://www.oracle.com/2014/03/ics/project"
NS_DEF  = "http://www.oracle.com/2014/03/ics/project/definition"  # default xmlns

# ── PlantUML web-server encoding ───────────────────────────────────────────────
# Custom base64 alphabet used by the PlantUML web server API — platform constant.
PUML_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz-_"
