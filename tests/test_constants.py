"""Tests for constants module."""

from oic_sequence_gen.constants import NS_DEF, NS_FLOW, NS_PROJ, PUML_ALPHABET


def test_namespaces_are_oracle_urls():
    for ns in (NS_FLOW, NS_PROJ, NS_DEF):
        assert ns.startswith("http://www.oracle.com/"), f"Unexpected namespace: {ns}"


def test_puml_alphabet_length_and_uniqueness():
    assert len(PUML_ALPHABET) == 64
    assert len(set(PUML_ALPHABET)) == 64
