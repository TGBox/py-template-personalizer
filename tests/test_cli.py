import pytest
from pathlib import Path
from template_personalizer.cli import main


def test_cli_dry_run():
    ret = main(["--dry-run", "--config", "config.example.yaml", "--input-dir", "testdata"])
    assert ret == 0


def test_cli_generate_config(tmp_path):
    out_cfg = tmp_path / "gen.yaml"
    ret = main(["--generate-config", str(out_cfg), "--input-dir", "testdata"])
    assert ret == 0
    assert out_cfg.is_file()
    assert "praxis:" in out_cfg.read_text(encoding="utf-8")


def test_cli_missing_config(tmp_path):
    ret = main(["--config", str(tmp_path / "missing.yaml"), "--input-dir", "testdata"])
    assert ret == 1


def test_cli_missing_input_dir():
    ret = main(["--config", "config.example.yaml", "--input-dir", "nonexistent_dir"])
    assert ret == 1


def test_cli_output_run(tmp_path):
    out_dir = tmp_path / "cli_output"
    ret = main(["--config", "config.example.yaml", "--input-dir", "testdata", "--output-dir", str(out_dir)])
    assert ret == 0
    assert out_dir.is_dir()
    assert len(list(out_dir.glob("*.fr3"))) == 44
