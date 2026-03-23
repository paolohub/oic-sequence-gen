# oic-sequence-gen

Generate **PlantUML**, **Mermaid Markdown**, and **PNG** sequence diagrams from
Oracle Integration Cloud (OIC) `.iar` export archives — with zero runtime dependencies.

```bash
# via uv (package install)
uv run oic-sequence-gen --input my_integration.iar --formats puml md png

# standalone — no install needed
python oic_sequence_gen_standalone.py --input my_integration.iar --formats puml md png
```

---

## Features

- Parses the `project.xml` orchestration tree inside any OIC `.iar` archive
- Reconstructs the full integration flow: loops, routers, try/catch/catchAll, stage files, external invocations, parallel branches, scopes, scheduled triggers, multi-event picks, stitches, notifications
- **Participants discovered dynamically** from `appinstances/*.xml` — no hardcoded connection names
- **Route conditions read from `expr.properties`** — labels come from the IAR, not from a lookup table
- **Supports all OIC integration patterns**: App-Driven Orchestration (REST/SOAP trigger), Scheduled, and multi-event Pick
- Outputs:
  - **PlantUML** (`.puml`) — fully styled with `skinparam`, `activate`/`deactivate`, colour-coded throws
  - **Mermaid Markdown** (`.md`) — ready to embed in GitHub / GitLab wikis
  - **PNG** — via local `plantuml` CLI or PlantUML web-server fallback
- **No runtime dependencies** — Python 3.9+ stdlib only

---

## Installation

### Option 1 — Standalone script (no install required)

Download [`oic_sequence_gen_standalone.py`](oic_sequence_gen_standalone.py) and run it directly with any Python 3.9+ interpreter — no virtual environment, no `pip install`, no dependencies of any kind.

```bash
python oic_sequence_gen_standalone.py --input my_integration.iar
```

### Option 2 — From source with uv

```bash
git clone https://github.com/paolohub/oic-sequence-gen.git
cd oic-sequence-gen
uv sync
```

This creates a `.venv` and installs the package inside it.

### Option 3 — Directly via uv without installing

```bash
uv run python -m oic_sequence_gen --input integration.iar
```

---

## Usage

Both the package command and the standalone script accept the same arguments:

```
usage: oic-sequence-gen [-h] --input INPUT [--output OUTPUT]
                        [--formats {puml,md,png} ...]

options:
  -h, --help            show this help message and exit
  --input  INPUT, -i    Path to the .iar file
  --output OUTPUT, -o   Output directory (default: same directory as --input)
  --formats FORMAT ..., -f
                        Output formats: puml, md, png  (default: puml md)
```

### Examples

```bash
# PlantUML + Mermaid Markdown (default) — standalone
python oic_sequence_gen_standalone.py --input integration.iar

# All three formats into a specific directory — standalone
python oic_sequence_gen_standalone.py --input integration.iar --output ./docs --formats puml md png

# Mermaid only — via uv package
uv run oic-sequence-gen -i integration.iar -f md
```

### Output files

| Format | File | Description |
|--------|------|-------------|
| `puml` | `sequence_diagram.puml` | PlantUML source with full skinparam styling |
| `md`   | `sequence_diagram.md`   | Mermaid `sequenceDiagram` inside a Markdown fence |
| `png`  | `sequence_diagram.png`  | Raster image (requires PlantUML or internet access) |

---

## PNG generation

PNG rendering requires one of:

1. **Local PlantUML CLI** — `plantuml` on `$PATH`, or `java -jar plantuml.jar`
   in the current directory or `/usr/share/plantuml/plantuml.jar`.
   Download: <https://plantuml.com/download>

2. **PlantUML web server** (automatic fallback) — sends the encoded diagram to
   `plantuml.com/plantuml/png/…`. This may fail for very large diagrams due to
   URL length limits.

---

## Programmatic API

```python
import zipfile, tempfile, shutil
from oic_sequence_gen import IARParser, generate_puml, generate_mermaid

work = tempfile.mkdtemp()
try:
    with zipfile.ZipFile("integration.iar") as zf:
        zf.extractall(work)

    parser = IARParser(work)
    parser.parse()

    puml = generate_puml(parser)
    md   = generate_mermaid(parser)
finally:
    shutil.rmtree(work)
```

### Key classes and functions

| Symbol | Module | Description |
|--------|--------|-------------|
| `IARParser` | `oic_sequence_gen.parser` | Parses the extracted archive; populates `parser.sequence` and `parser.participants` |
| `generate_puml(parser)` | `oic_sequence_gen.generators` | Returns PlantUML source string |
| `generate_mermaid(parser)` | `oic_sequence_gen.generators` | Returns Mermaid Markdown string |
| `generate_png(puml, path)` | `oic_sequence_gen.generators` | Writes PNG file; returns `True` on success |

---

## Supported OIC constructs

| XML element | Diagram representation |
|-------------|------------------------|
| `<receive>` | `Client ->> OIC : {BINDING} {op_name}` — binding and op name read from source application |
| `<scheduleReceive>` | `Scheduler ->> OIC : Scheduled trigger` — adds `OIC Scheduler` actor |
| `<pick>` / `<pickReceive>` | `alt {op_name} … else … end` — one branch per `<pickReceive>`, op name from application |
| `<invoke>` | Arrow to target participant; label is `op_name (operation)` — both read from the target application |
| `<reply>` | `OIC -->> Client : {op_name}` — async reply, op name read from application |
| `<stitch>` | `OIC ->> OIC : STITCH {processor name}` — integration-to-integration call |
| `<stageFile>` | Arrow to `StageFile (OIC)` built-in participant; label is the processor name |
| `<for>` / `<while>` | `loop {processor name} … end` block |
| `<router>` / `<route>` | `alt {condition} … else … end` — conditions read from `expr.properties` |
| `<scope>` | `group scope: {name} … end` block |
| `<parallel>` / `<branch>` | `par {branch name} … else/and … end` block |
| `<try>` / `<catch>` / `<catchAll>` | `group try: {name} … end` + `alt Catch/CatchAll: {name} … end` |
| `<throw>` | Red arrow `OIC -[#red]-> Client : THROW {fault name}` |
| `<stop>` | `OIC --> Client : 200 OK` (REST trigger) or `success` (other bindings) |
| `<ehStop>` | Red arrow `OIC -[#red]-> Client : Generic error (ehStop)` |
| `<assignment>` / `<label>` | `OIC ->> OIC : ASSIGN {processor name}` |
| `<transformer>` (named) | `OIC ->> OIC : Transformer — {processor name}` |
| `<wait>` | `OIC ->> OIC : WAIT ({processor name})` |
| `<activityStreamLogger>` | `OIC ->> OIC : ActivityStreamLogger ({processor name})` |
| `<notification>` | `OIC ->> OIC : Notification ({processor name})` |
| `<note>` (designer annotation) | Note box with `description` / `name` attribute text |

---

## How participants and conditions are resolved

The tool requires **no configuration** for any specific integration.

### Participants

Each connection declared in `appinstances/*.xml` becomes a diagram participant
automatically.  The alias is derived from the `<applicationTypeRef>` value
(e.g., `hcm` → `HCM`, `ftp` → `FTP`); the display label is taken from the
connection's `<displayName>`.  Multiple connections of the same technology type
get a numeric suffix (`FTP`, `FTP_2`, …).

### Route condition labels

Labels are read from the `ExpressionName` field in each route's `expr.properties`
file (stored inside the IAR under `resources/`).  If `ExpressionName` is blank,
the `TextExpression` (XPath) is used instead.  No manual mapping is required.

---

## Development

```bash
# Install with dev extras
uv sync --dev

# Run tests
uv run pytest tests/ -v

# Lint
uv run ruff check src/ tests/

# Regenerate the standalone script after source changes
python build_standalone.py
```

### Running integration tests

Place one or more real `.iar` files under `tests/fixtures/`.
Integration tests skip automatically when no fixture is present.

---

## Project structure

```
oic-sequence-gen/
├── src/
│   └── oic_sequence_gen/
│       ├── __init__.py          # public API + __version__
│       ├── __main__.py          # python -m oic_sequence_gen
│       ├── constants.py         # XML namespaces + PlantUML encoding alphabet
│       ├── parser.py            # IARParser class
│       ├── cli.py               # argparse entry point
│       └── generators/
│           ├── __init__.py      # re-exports generate_puml/mermaid/png
│           ├── plantuml.py      # PlantUML + web-encoding helper
│           ├── mermaid.py       # Mermaid Markdown
│           └── png.py           # PNG via local CLI or web fallback
├── tests/
│   ├── test_constants.py
│   ├── test_parser.py
│   └── test_generators.py
├── examples/
│   └── sample/
│       ├── sequence_diagram.puml
│       └── sequence_diagram.md
├── oic_sequence_gen_standalone.py  # single-file standalone version (auto-generated)
├── build_standalone.py             # script that regenerates the standalone file
├── pyproject.toml
├── uv.lock
├── CHANGELOG.md
└── LICENSE
```

---

## License

MIT — see [LICENSE](LICENSE).
