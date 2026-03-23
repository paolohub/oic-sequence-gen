"""
cli.py — Command-line interface for oic-sequence-gen.

Entry point registered in pyproject.toml:
    [project.scripts]
    oic-sequence-gen = "oic_sequence_gen.cli:main"
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

from oic_sequence_gen.generators import generate_mermaid, generate_png, generate_puml
from oic_sequence_gen.parser import IARParser


def main() -> None:
    arg_parser = argparse.ArgumentParser(
        prog="oic-sequence-gen",
        description="Generate sequence diagrams from Oracle Integration Cloud (.iar) archives",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
Examples:
  oic-sequence-gen --input my_integration.iar
  oic-sequence-gen --input integration.iar --formats puml md png
  oic-sequence-gen --input integration.iar --output ./docs --formats puml md
""",
    )
    arg_parser.add_argument(
        "--input", "-i", required=True,
        help="Path to the .iar file",
    )
    arg_parser.add_argument(
        "--output", "-o", default=None,
        help="Output directory (default: same directory as --input)",
    )
    arg_parser.add_argument(
        "--formats", "-f", nargs="+", default=["puml", "md"],
        choices=["puml", "md", "png"],
        help="Output formats: puml (PlantUML), md (Mermaid Markdown), png",
    )
    args = arg_parser.parse_args()

    iar_path = Path(args.input)
    if not iar_path.exists():
        print(f"ERROR: File not found: {iar_path}", file=sys.stderr)
        sys.exit(1)
    if not zipfile.is_zipfile(iar_path):
        print(f"ERROR: Not a valid ZIP/IAR archive: {iar_path}", file=sys.stderr)
        sys.exit(1)

    out_dir = Path(args.output) if args.output else iar_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    # ── Extract to a temporary directory ──────────────────────────────────────
    work_dir = tempfile.mkdtemp(prefix="oic_iar_")
    print(f"Extracting {iar_path.name} ...")
    try:
        with zipfile.ZipFile(iar_path, "r") as zf:
            zf.extractall(work_dir)

        # ── Parse ──────────────────────────────────────────────────────────────
        print("Parsing integration flow ...")
        parser = IARParser(work_dir)
        parser.parse()
        print(f"  Project : {parser.project_code} v{parser.project_version}")
        print(f"  Name    : {parser.project_name}")
        print(f"  Steps   : {len(parser.sequence)} sequence events")

        # ── Generate requested formats ─────────────────────────────────────────
        puml_content: str | None = None

        for fmt in args.formats:
            if fmt == "puml":
                content = generate_puml(parser)
                out_path = out_dir / "sequence_diagram.puml"
                out_path.write_text(content, encoding="utf-8")
                print(f"  [puml]  -> {out_path}")
                puml_content = content

            elif fmt == "md":
                content = generate_mermaid(parser)
                out_path = out_dir / "sequence_diagram.md"
                out_path.write_text(content, encoding="utf-8")
                print(f"  [md]    -> {out_path}")

            elif fmt == "png":
                if puml_content is None:
                    puml_content = generate_puml(parser)
                out_path = out_dir / "sequence_diagram.png"
                ok = generate_png(puml_content, str(out_path))
                if ok:
                    print(f"  [png]   -> {out_path}")
                else:
                    print("  [png]   FAILED — see errors above", file=sys.stderr)

        print("Done.")

    finally:
        print("Cleaning up temporary files ...")
        shutil.rmtree(work_dir, ignore_errors=True)
