"""
Tests for IARParser.

Integration tests require a real .iar file; they are skipped automatically
when the fixture is absent so the CI matrix stays green without binary fixtures.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from oic_sequence_gen.parser import IARParser, _local, _t, _td

# ── Unit tests for XML helpers ─────────────────────────────────────────────────

def test_t_default_namespace():
    result = _t("application")
    assert result == "{http://www.oracle.com/2014/03/ics/flow/definition}application"


def test_td_default_namespace():
    result = _td("projectCode")
    assert result == "{http://www.oracle.com/2014/03/ics/project/definition}projectCode"


def test_local_strips_namespace():
    assert _local("{http://example.com}foo") == "foo"


def test_local_passthrough_when_no_namespace():
    assert _local("bar") == "bar"


# ── Integration test against a real .iar ──────────────────────────────────────

def _find_any_iar() -> Path | None:
    """Return the first .iar file found in tests/fixtures/, or None."""
    fixtures = Path(__file__).parent / "fixtures"
    iars = sorted(fixtures.glob("*.iar"))
    return iars[0] if iars else None


@pytest.fixture(scope="module")
def parsed_iar(tmp_path_factory):
    fixture = _find_any_iar()
    if fixture is None:
        pytest.skip("No .iar fixture found in tests/fixtures/")
    work = tmp_path_factory.mktemp("iar_work")
    with zipfile.ZipFile(fixture, "r") as zf:
        zf.extractall(work)
    parser = IARParser(str(work))
    parser.parse()
    return parser


def test_project_code(parsed_iar):
    assert parsed_iar.project_code, "project_code must not be empty"


def test_project_version(parsed_iar):
    import re
    assert re.match(r"\d+\.\d+\.\d+", parsed_iar.project_version), (
        f"Unexpected version format: {parsed_iar.project_version!r}"
    )


def test_sequence_is_non_empty(parsed_iar):
    assert len(parsed_iar.sequence) > 0


def test_sequence_starts_with_trigger(parsed_iar):
    first = parsed_iar.sequence[0]
    assert first["type"] == "invoke"
    assert first.get("is_trigger") is True
    assert first["from"] == "Client"
    assert first["to"] == "OIC"


def test_sequence_contains_external_invoke(parsed_iar):
    """At least one invoke must target a participant other than OIC/Client."""
    external = [
        s for s in parsed_iar.sequence
        if s["type"] == "invoke" and s.get("to") not in ("OIC", "Client", "StageFile")
    ]
    assert external, "Expected at least one external (non-OIC) invoke in the sequence"


def test_participants_built_dynamically(parsed_iar):
    """Participants must include Client + OIC plus at least one discovered connection."""
    aliases = {p[0] for p in parsed_iar.participants}
    assert "Client" in aliases
    assert "OIC"    in aliases
    assert len(parsed_iar.participants) > 2, "No dynamic participants discovered"


def test_participants_kinds_are_valid(parsed_iar):
    for alias, kind, label in parsed_iar.participants:
        assert kind in ("actor", "participant"), f"Bad kind {kind!r} for {alias}"
        assert label, f"Empty label for {alias}"


def test_sequence_ends_with_response_or_throw(parsed_iar):
    # Last meaningful step before the global catchAll should be a response or throw
    non_section = [s for s in parsed_iar.sequence if s["type"] not in ("section", "note")]
    last = non_section[-1]
    assert last["type"] in ("response", "throw")


def test_loop_blocks_are_balanced(parsed_iar):
    starts = sum(1 for s in parsed_iar.sequence if s["type"] == "loop_start")
    ends   = sum(1 for s in parsed_iar.sequence if s["type"] == "loop_end")
    assert starts == ends, f"Unbalanced loop blocks: {starts} starts, {ends} ends"


def test_alt_blocks_are_balanced(parsed_iar):
    branches = sum(1 for s in parsed_iar.sequence if s["type"] == "alt_branch" and s["kw"] == "alt")
    ends     = sum(1 for s in parsed_iar.sequence if s["type"] == "alt_end")
    assert branches == ends, f"Unbalanced alt blocks: {branches} alts, {ends} ends"
