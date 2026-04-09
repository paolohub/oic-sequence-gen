"""
Tests for the CLI entry point (cli.py).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from oic_sequence_gen.cli import main


# ── Helpers ────────────────────────────────────────────────────────────────────

FIXTURE_IAR = Path(__file__).parent / "fixtures" / "ST_INB_JOB_PROF_SKIL_UPLD_027_01.00.0000.iar"


def _run(args: list[str], monkeypatch) -> None:
    """Invoke main() with the given argument list."""
    import sys
    monkeypatch.setattr(sys, "argv", ["oic-sequence-gen"] + args)
    main()


# ── Default output name ────────────────────────────────────────────────────────

class TestDefaultName:
    def test_default_puml_name(self, tmp_path, monkeypatch):
        _run(["--input", str(FIXTURE_IAR), "--output", str(tmp_path), "--formats", "puml"], monkeypatch)
        assert (tmp_path / "sequence_diagram.puml").exists()

    def test_default_md_name(self, tmp_path, monkeypatch):
        _run(["--input", str(FIXTURE_IAR), "--output", str(tmp_path), "--formats", "md"], monkeypatch)
        assert (tmp_path / "sequence_diagram.md").exists()

    def test_default_both_formats(self, tmp_path, monkeypatch):
        _run(["--input", str(FIXTURE_IAR), "--output", str(tmp_path), "--formats", "puml", "md"], monkeypatch)
        assert (tmp_path / "sequence_diagram.puml").exists()
        assert (tmp_path / "sequence_diagram.md").exists()


# ── Custom output name (--name) ────────────────────────────────────────────────

class TestCustomName:
    def test_custom_puml_name(self, tmp_path, monkeypatch):
        _run(["--input", str(FIXTURE_IAR), "--output", str(tmp_path),
              "--formats", "puml", "--name", "my_diagram"], monkeypatch)
        assert (tmp_path / "my_diagram.puml").exists()
        assert not (tmp_path / "sequence_diagram.puml").exists()

    def test_custom_md_name(self, tmp_path, monkeypatch):
        _run(["--input", str(FIXTURE_IAR), "--output", str(tmp_path),
              "--formats", "md", "--name", "my_diagram"], monkeypatch)
        assert (tmp_path / "my_diagram.md").exists()
        assert not (tmp_path / "sequence_diagram.md").exists()

    def test_custom_name_both_formats(self, tmp_path, monkeypatch):
        _run(["--input", str(FIXTURE_IAR), "--output", str(tmp_path),
              "--formats", "puml", "md", "--name", "custom_out"], monkeypatch)
        assert (tmp_path / "custom_out.puml").exists()
        assert (tmp_path / "custom_out.md").exists()

    def test_short_flag_n(self, tmp_path, monkeypatch):
        _run(["--input", str(FIXTURE_IAR), "--output", str(tmp_path),
              "--formats", "puml", "-n", "short_flag"], monkeypatch)
        assert (tmp_path / "short_flag.puml").exists()


# ── Error handling ─────────────────────────────────────────────────────────────

class TestErrors:
    def test_missing_input_exits(self, monkeypatch):
        import sys
        monkeypatch.setattr(sys, "argv", ["oic-sequence-gen", "--input", "nonexistent.iar"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0

    def test_invalid_zip_exits(self, tmp_path, monkeypatch):
        bad = tmp_path / "bad.iar"
        bad.write_text("not a zip", encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["oic-sequence-gen", "--input", str(bad)])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code != 0
