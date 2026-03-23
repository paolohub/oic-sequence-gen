"""
oic-sequence-gen — Generate PlantUML / Mermaid / PNG sequence diagrams
from Oracle Integration Cloud (.iar) archives.

Programmatic API
----------------
>>> from oic_sequence_gen import IARParser, generate_puml, generate_mermaid
>>> import zipfile, tempfile, shutil
>>>
>>> work = tempfile.mkdtemp()
>>> try:
...     with zipfile.ZipFile("integration.iar") as zf:
...         zf.extractall(work)
...     parser = IARParser(work)
...     parser.parse()
...     puml = generate_puml(parser)
... finally:
...     shutil.rmtree(work)
"""

__version__ = "0.1.0"

from oic_sequence_gen.generators import generate_mermaid, generate_png, generate_puml
from oic_sequence_gen.parser import IARParser

__all__ = [
    "IARParser",
    "generate_puml",
    "generate_mermaid",
    "generate_png",
    "__version__",
]
