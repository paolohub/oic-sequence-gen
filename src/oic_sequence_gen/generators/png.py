"""
generators/png.py — Generate a PNG from PlantUML source.

Strategy (in order):
  1. Local ``plantuml`` CLI on PATH
  2. ``java -jar plantuml.jar`` in common locations
  3. PlantUML public web-server API (GET request, may fail for very large diagrams)
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

from oic_sequence_gen.generators.plantuml import _encode_plantuml


def generate_png(puml_content: str, output_path: str) -> bool:
    """
    Write a PNG rendering of *puml_content* to *output_path*.

    Returns ``True`` on success, ``False`` on failure (warnings are printed to
    stderr but no exception is raised so callers can degrade gracefully).
    """
    # ── Strategy 1: local plantuml executable ─────────────────────────────────
    plantuml_cmd = shutil.which("plantuml")

    # ── Strategy 2: java -jar plantuml.jar ────────────────────────────────────
    if not plantuml_cmd and shutil.which("java"):
        for jar in [
            "plantuml.jar",
            "/usr/share/plantuml/plantuml.jar",
            "/usr/local/lib/plantuml.jar",
            str(Path.home() / "plantuml.jar"),
        ]:
            if os.path.exists(jar):
                plantuml_cmd = f"java -jar {jar}"
                break

    if plantuml_cmd:
        return _run_local(plantuml_cmd, puml_content, output_path)

    # ── Strategy 3: web-server fallback ───────────────────────────────────────
    print("  plantuml not found locally — trying PlantUML web server ...", file=sys.stderr)
    return _run_web(puml_content, output_path)


# ── Internal helpers ───────────────────────────────────────────────────────────

def _run_local(plantuml_cmd: str, puml_content: str, output_path: str) -> bool:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".puml", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(puml_content)
        tmp_path = tmp.name

    try:
        out_dir = str(Path(output_path).parent)
        if plantuml_cmd.startswith("java"):
            cmd = plantuml_cmd.split() + ["-tpng", "-o", out_dir, tmp_path]
        else:
            cmd = [plantuml_cmd, "-tpng", "-o", out_dir, tmp_path]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  plantuml error: {result.stderr}", file=sys.stderr)
            return False

        # plantuml writes <input>.png in the same directory; move it
        generated = Path(tmp_path).with_suffix(".png")
        if generated.exists():
            shutil.move(str(generated), output_path)
        return Path(output_path).exists()
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def _run_web(puml_content: str, output_path: str) -> bool:
    try:
        encoded = _encode_plantuml(puml_content)
        url = f"https://www.plantuml.com/plantuml/png/{encoded}"
        urllib.request.urlretrieve(url, output_path)
        return True
    except Exception as exc:
        print(f"  Web server PNG generation failed: {exc}", file=sys.stderr)
        print(
            "  Install PlantUML locally: https://plantuml.com/download",
            file=sys.stderr,
        )
        return False
