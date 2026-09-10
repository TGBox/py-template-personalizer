import json
import pytest
from pathlib import Path
from template_personalizer.config import PersonalizerConfig, load_config, to_pascal_literal


def test_config_lookup_case_insensitive():
    cfg = PersonalizerConfig({
        "praxis": {
            "name": "Praxis Dr. Test",
            "plz": "12345"
        }
    })
    assert cfg.has_field("praxis", "name")
    assert cfg.has_field("PRAXIS", "NAME")
    assert cfg.get_value("praxis", "name") == "Praxis Dr. Test"
    assert cfg.get_value("PRAXIS", "name") == "Praxis Dr. Test"
    assert cfg.get_value("praxis", "PLZ") == "12345"
    assert cfg.get_value("praxis", "unknown") is None


def test_pascal_literal_escaping():
    assert to_pascal_literal("Hello") == "'Hello'"
    assert to_pascal_literal("Dr. O'Reilly & Partner") == "'Dr. O''Reilly & Partner'"
    assert to_pascal_literal("") == "''"


def test_config_pascal_literal():
    cfg = PersonalizerConfig({
        "praxis": {
            "bic": "GENODEF1MST",
            "name": "Praxis O'Connor"
        }
    })
    assert cfg.get_pascal_literal("praxis", "bic") == "'GENODEF1MST'"
    assert cfg.get_pascal_literal("praxis", "name") == "'Praxis O''Connor'"
    assert cfg.get_pascal_literal("praxis", "missing") is None


def test_load_yaml_config(tmp_path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(
        "praxis:\n  name: 'Muster'\n  ort: 'Berlin'\nlogo:\n  filename: 'logo.png'\n",
        encoding="utf-8"
    )
    cfg = load_config(yaml_file)
    assert cfg.get_value("praxis", "name") == "Muster"
    assert cfg.get_value("praxis", "ort") == "Berlin"
    assert cfg.get_value("logo", "filename") == "logo.png"
    assert "praxis" in cfg.tables()
    assert "logo" in cfg.tables()


def test_load_json_config(tmp_path):
    json_file = tmp_path / "config.json"
    json_file.write_text(
        json.dumps({"praxis": {"name": "Test", "iban": "DE123"}}),
        encoding="utf-8"
    )
    cfg = load_config(json_file)
    assert cfg.get_value("praxis", "name") == "Test"
    assert cfg.get_value("praxis", "iban") == "DE123"


def test_load_nonexistent_config():
    with pytest.raises(FileNotFoundError):
        load_config("nonexistent_file_path.yaml")


def test_load_invalid_config(tmp_path):
    invalid_file = tmp_path / "invalid.json"
    invalid_file.write_text("['not', 'a', 'dict']", encoding="utf-8")
    with pytest.raises(ValueError):
        load_config(invalid_file)
