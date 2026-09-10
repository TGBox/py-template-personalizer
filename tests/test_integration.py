import os
import xml.etree.ElementTree as ET
from pathlib import Path
from template_personalizer.config import load_config
from template_personalizer.personalizer import TemplatePersonalizer


def test_full_integration_on_testdata(tmp_path):
    config_path = Path("config.example.yaml")
    assert config_path.is_file(), "config.example.yaml must exist"

    cfg = load_config(config_path)
    personalizer = TemplatePersonalizer(cfg)

    input_dir = Path("testdata")
    output_dir = tmp_path / "output_test"

    stats = personalizer.personalize_directory(
        input_dir=input_dir,
        output_dir=output_dir,
        pattern="*.fr3",
        in_place=False,
        dry_run=False
    )

    assert stats.files_processed == 44
    assert stats.files_modified > 30
    assert stats.total_replacements > 300
    assert stats.memos_unbound > 100

    # Verify that all 44 output files exist and are valid XML
    output_files = list(output_dir.glob("*.fr3"))
    assert len(output_files) == 44

    for out_file in output_files:
        with open(out_file, "r", encoding="utf-8") as f:
            content = f.read()
        assert content.startswith('<?xml version="1.0" encoding="utf-8" standalone="no"?>')
        # ElementTree must parse without syntax error
        tree = ET.fromstring(content)
        assert tree.tag == "TfrxReport"

    # Spot check: Behandlungsbestaetigung_Behandlungsbestätigung.fr3
    target_bb = output_dir / "Behandlungsbestaetigung_Behandlungsbestätigung.fr3"
    assert target_bb.is_file()
    tree_bb = ET.parse(target_bb)
    for memo in tree_bb.findall(".//TfrxMemoView"):
        name = memo.attrib.get("Name")
        if name == "praxisname1":
            assert memo.attrib["Text"] == "Praxis für Physiotherapie Mustermann"
            assert "DataSet" not in memo.attrib
            assert "DataField" not in memo.attrib
        elif name == "praxisplz":
            assert "Gesundheitsstraße 42, 89073 Ulm" in memo.attrib["Text"]

    # Spot check: Faktura_Rechnung-DINA4.fr3
    target_rechnung = output_dir / "Faktura_Rechnung-DINA4.fr3"
    assert target_rechnung.is_file()
    tree_rechnung = ET.parse(target_rechnung)
    root_rechnung = tree_rechnung.getroot()
    # Check script text replacement
    assert "'praxis_logo.png'" in root_rechnung.attrib["ScriptText.Text"]
    assert "'GENODEF1ULM'" in root_rechnung.attrib["ScriptText.Text"]

    # Check barcode
    barcode = tree_rechnung.find(".//TfrxBarcode2DView")
    assert barcode is not None
    assert "DE02630901440012345678" in barcode.attrib["Expression"]
