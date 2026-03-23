"""
Tests for generator functions.

When the IAR fixture is present the generators are exercised end-to-end;
otherwise only structural / smoke tests run against a hand-crafted sequence.
"""

from __future__ import annotations

import zipfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from oic_sequence_gen.generators import generate_mermaid, generate_puml
from oic_sequence_gen.generators.plantuml import _encode_plantuml
from oic_sequence_gen.parser import IARParser

# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_minimal_parser() -> IARParser:
    """Return a parser-like object with a minimal hand-crafted sequence."""
    p = MagicMock(spec=IARParser)
    p.project_code    = "TEST_INTEGRATION"
    p.project_name    = "Test Integration"
    p.project_version = "01.00.0000"
    p.participants = [
        ("Client",    "actor",       "Client"),
        ("OIC",       "participant", "OIC Integration"),
        ("HCM",       "participant", "HCM Cloud"),
        ("SFTP",      "participant", "SFTP Server"),
        ("StageFile", "participant", "Stage File (OIC)"),
        ("OICInst",   "participant", "OIC Internal"),
    ]
    p.sequence = [
        {"type": "invoke",   "from": "Client", "to": "OIC",   "msg": "POST /trigger", "ret": "", "is_trigger": True},
        {"type": "internal", "actor": "OIC",   "msg": "MessageTracker + IntegrationMetadata"},
        {"type": "invoke",   "from": "OIC",    "to": "HCM",   "msg": "importAndLoadData", "ret": ""},
        {"type": "response", "from": "OIC",    "to": "Client", "msg": "200 OK"},
    ]
    return p


# ── PlantUML generator tests ───────────────────────────────────────────────────

class TestGeneratePuml:
    def test_starts_with_startuml(self):
        puml = generate_puml(_make_minimal_parser())
        assert puml.startswith("@startuml TEST_INTEGRATION")

    def test_ends_with_enduml(self):
        puml = generate_puml(_make_minimal_parser())
        assert puml.strip().endswith("@enduml")

    def test_contains_all_participants(self):
        puml = generate_puml(_make_minimal_parser())
        for alias in ("Client", "OIC", "HCM", "SFTP", "StageFile", "OICInst"):
            assert alias in puml, f"Participant {alias!r} missing from PlantUML output"

    def test_trigger_activates_oic(self):
        puml = generate_puml(_make_minimal_parser())
        assert "activate OIC" in puml

    def test_response_deactivates_oic(self):
        puml = generate_puml(_make_minimal_parser())
        assert "deactivate OIC" in puml

    def test_loop_block(self):
        p = _make_minimal_parser()
        p.sequence = [
            {"type": "loop_start", "label": "ForEachFile"},
            {"type": "internal",   "actor": "OIC", "msg": "ASSIGN x"},
            {"type": "loop_end"},
        ]
        puml = generate_puml(p)
        assert "loop ForEachFile" in puml
        assert puml.count("end") >= 1

    def test_alt_block(self):
        p = _make_minimal_parser()
        p.sequence = [
            {"type": "alt_branch", "kw": "alt",  "cond": "FilesFound"},
            {"type": "internal",   "actor": "OIC", "msg": "ASSIGN x"},
            {"type": "alt_branch", "kw": "else", "cond": "NoFiles"},
            {"type": "throw",      "from": "OIC", "to": "Client", "msg": "EmptyFileException"},
            {"type": "alt_end"},
        ]
        puml = generate_puml(p)
        assert "alt FilesFound" in puml
        assert "else NoFiles" in puml

    def test_throw_uses_red_arrow(self):
        p = _make_minimal_parser()
        p.sequence = [
            {"type": "throw", "from": "OIC", "to": "Client", "msg": "SomeException"},
        ]
        puml = generate_puml(p)
        assert "-[#red]->" in puml
        assert "THROW** SomeException" in puml


# ── Mermaid generator tests ────────────────────────────────────────────────────

class TestGenerateMermaid:
    def test_contains_mermaid_fence(self):
        md = generate_mermaid(_make_minimal_parser())
        assert "```mermaid" in md
        assert md.strip().endswith("```")

    def test_contains_sequencediagram(self):
        md = generate_mermaid(_make_minimal_parser())
        assert "sequenceDiagram" in md

    def test_contains_autonumber(self):
        md = generate_mermaid(_make_minimal_parser())
        assert "autonumber" in md

    def test_contains_all_participants(self):
        md = generate_mermaid(_make_minimal_parser())
        for alias in ("Client", "OIC", "HCM", "SFTP", "StageFile", "OICInst"):
            assert alias in md


# ── PlantUML encoding tests ────────────────────────────────────────────────────

class TestEncodePlantuml:
    def test_returns_non_empty_string(self):
        encoded = _encode_plantuml("@startuml\nA -> B: hello\n@enduml")
        assert isinstance(encoded, str)
        assert len(encoded) > 0

    def test_only_valid_alphabet_chars(self):
        from oic_sequence_gen.constants import PUML_ALPHABET
        encoded = _encode_plantuml("@startuml\nA -> B: test\n@enduml")
        for ch in encoded:
            assert ch in PUML_ALPHABET, f"Invalid character {ch!r} in encoded output"


# ── End-to-end integration test ───────────────────────────────────────────────

def _find_any_iar() -> Path | None:
    """Return the first .iar file found in tests/fixtures/, or None."""
    fixtures = Path(__file__).parent / "fixtures"
    iars = sorted(fixtures.glob("*.iar"))
    return iars[0] if iars else None


@pytest.fixture(scope="module")
def full_parser(tmp_path_factory):
    fixture = _find_any_iar()
    if fixture is None:
        pytest.skip("No .iar fixture found in tests/fixtures/")
    work = tmp_path_factory.mktemp("iar_work_gen")
    with zipfile.ZipFile(fixture, "r") as zf:
        zf.extractall(work)
    parser = IARParser(str(work))
    parser.parse()
    return parser


def test_e2e_puml_is_valid_structure(full_parser):
    puml = generate_puml(full_parser)
    assert puml.startswith("@startuml")
    assert puml.strip().endswith("@enduml")
    assert "\n-" not in puml.replace("-[#red]->", "")


def test_e2e_mermaid_fence_balanced(full_parser):
    md = generate_mermaid(full_parser)
    fences = md.count("```")
    assert fences == 2, f"Expected 2 fence markers, got {fences}"


def test_e2e_participants_built_dynamically(full_parser):
    """Participants must be derived from the IAR, not from hardcoded constants."""
    aliases = {p[0] for p in full_parser.participants}
    # Fixed endpoints always present
    assert "Client" in aliases
    assert "OIC"    in aliases
    # At least one dynamically-discovered participant
    assert len(full_parser.participants) > 2


def test_e2e_no_hardcoded_italian(full_parser):
    """Route conditions must come from expr.properties, not from a lookup table."""
    puml = generate_puml(full_parser)
    for italian_phrase in ("File trovati", "Nessun file", "Istanza gia'", "Import completato"):
        assert italian_phrase not in puml, (
            f"Hardcoded Italian phrase {italian_phrase!r} found — "
            "route conditions should come from the IAR, not constants.py"
        )
