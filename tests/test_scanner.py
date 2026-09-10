from pathlib import Path
from template_personalizer.scanner import TemplateScanner


def test_scanner_directory():
    discovered = TemplateScanner.scan_directory("testdata")
    assert "praxis" in discovered
    assert "logo" in discovered
    assert "name" in discovered["praxis"]
    assert "iban" in discovered["praxis"]
    assert "filename" in discovered["logo"]


def test_scanner_generate_config_template():
    tpl = TemplateScanner.generate_config_template("testdata")
    assert "praxis" in tpl
    assert "logo" in tpl
    assert "name" in tpl["praxis"]
    assert "filename" in tpl["logo"]
