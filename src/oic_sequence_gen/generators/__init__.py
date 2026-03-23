"""
generators — Output format sub-package.

Re-exports the three public generator functions so callers can write:
    from oic_sequence_gen.generators import generate_puml, generate_mermaid, generate_png
"""

from oic_sequence_gen.generators.mermaid import generate_mermaid
from oic_sequence_gen.generators.plantuml import generate_puml
from oic_sequence_gen.generators.png import generate_png

__all__ = ["generate_puml", "generate_mermaid", "generate_png"]
