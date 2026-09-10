import xml.etree.ElementTree as ET
from template_personalizer.config import PersonalizerConfig
from template_personalizer.personalizer import TemplatePersonalizer


def test_memo_text_replacement():
    cfg = PersonalizerConfig({
        "praxis": {
            "name": "Praxis Dr. Test",
            "strasse": "Hauptstr. 10",
            "plz": "10115",
            "ort": "Berlin",
        }
    })
    personalizer = TemplatePersonalizer(cfg)

    xml = (
        '<TfrxReport Version="2025.1.7">'
        '  <TfrxReportPage Name="Page1">'
        '    <TfrxMemoView Name="Memo1" Text="[praxis.&#34;name&#34;]"/>'
        '    <TfrxMemoView Name="Memo2" Text="[praxis.&#34;strasse&#34;], [praxis.&#34;plz&#34;] [praxis.&#34;ort&#34;]"/>'
        '    <TfrxMemoView Name="Memo3" Text="&#60;b&#62;[praxis.&#34;name&#34;]&#60;/b&#62;"/>'
        '  </TfrxReportPage>'
        '</TfrxReport>'
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    stats = personalizer.personalize_tree(tree, "test.fr3")

    assert stats.files_modified == 1
    assert stats.total_replacements == 5
    assert stats.replacements_per_field["praxis.name"] == 2
    assert stats.replacements_per_field["praxis.strasse"] == 1
    assert stats.replacements_per_field["praxis.plz"] == 1
    assert stats.replacements_per_field["praxis.ort"] == 1

    root = tree.getroot()
    memos = {m.attrib["Name"]: m.attrib["Text"] for m in root.findall(".//TfrxMemoView")}
    assert memos["Memo1"] == "Praxis Dr. Test"
    assert memos["Memo2"] == "Hauptstr. 10, 10115 Berlin"
    assert memos["Memo3"] == "<b>Praxis Dr. Test</b>"


def test_memo_binding_removal_when_fully_personalized():
    cfg = PersonalizerConfig({
        "praxis": {
            "name": "Praxis Dr. Test",
        }
    })
    personalizer = TemplatePersonalizer(cfg)

    xml = (
        '<TfrxReport Version="2025.1.7">'
        '  <TfrxReportPage Name="Page1">'
        '    <TfrxMemoView Name="MemoBound" DataSet="praxis" DataSetName="praxis" DataField="name" Text="[praxis.&#34;name&#34;]">'
        '      <Formats><item/></Formats>'
        '    </TfrxMemoView>'
        '  </TfrxReportPage>'
        '</TfrxReport>'
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    stats = personalizer.personalize_tree(tree, "test.fr3")

    assert stats.memos_unbound == 1
    root = tree.getroot()
    memo = root.find(".//TfrxMemoView")
    assert "DataSet" not in memo.attrib
    assert "DataSetName" not in memo.attrib
    assert "DataField" not in memo.attrib
    assert memo.find("Formats") is None
    assert memo.attrib["Text"] == "Praxis Dr. Test"


def test_memo_binding_preserved_if_unrelated_dataset():
    cfg = PersonalizerConfig({
        "praxis": {
            "ort": "Berlin"
        }
    })
    personalizer = TemplatePersonalizer(cfg)

    xml = (
        '<TfrxReport Version="2025.1.7">'
        '  <TfrxReportPage Name="Page1">'
        '    <TfrxMemoView Name="MemoMixed" DataSet="rechnung" DataSetName="rechnung" DataField="rechnungsdatum" Text="[praxis.&#34;ort&#34;], [rechnung.&#34;rechnungsdatum&#34;]"/>'
        '  </TfrxReportPage>'
        '</TfrxReport>'
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    personalizer.personalize_tree(tree, "test.fr3")

    root = tree.getroot()
    memo = root.find(".//TfrxMemoView")
    assert memo.attrib["DataSet"] == "rechnung"
    assert memo.attrib["DataField"] == "rechnungsdatum"
    assert memo.attrib["Text"] == 'Berlin, [rechnung."rechnungsdatum"]'


def test_pascal_script_and_barcode_replacement():
    cfg = PersonalizerConfig({
        "praxis": {
            "bic": "GENODEF1MST",
            "iban": "DE12345678",
            "unternehmen": "Praxis GmbH",
        },
        "logo": {
            "filename": "my_logo.png"
        }
    })
    personalizer = TemplatePersonalizer(cfg)

    xml = (
        '<TfrxReport Version="2025.1.7" ScriptText.Text="if fileexists(uploadpath + &#60;logo.&#34;filename&#34;&#62;) then Barcode.visible := (&#60;praxis.&#34;iban&#34;&#62; &#60;&#62; \'\');">'
        '  <TfrxReportPage Name="Page1">'
        '    <TfrxBarcode2DView Name="Barcode2D1" Expression="trim(&#60;praxis.&#34;iban&#34;&#62;)"/>'
        '    <TfrxMemoView Name="MemoWarn" Highlight.Condition="&#60;praxis.&#34;bic&#34;&#62; = \'\'" Text="Warning"/>'
        '  </TfrxReportPage>'
        '</TfrxReport>'
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    stats = personalizer.personalize_tree(tree, "test.fr3")

    root = tree.getroot()
    script = root.attrib["ScriptText.Text"]
    assert "'my_logo.png'" in script
    assert "'DE12345678'" in script
    assert '<logo."filename">' not in script

    barcode = root.find(".//TfrxBarcode2DView")
    assert barcode.attrib["Expression"] == "'DE12345678'"

    memo_warn = root.find(".//TfrxMemoView")
    assert memo_warn.attrib["Highlight.Condition"] == "'GENODEF1MST' = ''"


def test_literal_concatenation_simplification():
    cfg = PersonalizerConfig({
        "praxis": {
            "plz": "89073",
            "ort": "Ulm"
        }
    })
    personalizer = TemplatePersonalizer(cfg)

    xml = (
        '<TfrxReport Version="2025.1.7">'
        '  <TfrxReportPage Name="Page1">'
        '    <TfrxMemoView Name="MemoConcat" Text="[&#60;praxis.&#34;plz&#34;&#62;+\' \'+&#60;praxis.&#34;ort&#34;&#62;]"/>'
        '  </TfrxReportPage>'
        '</TfrxReport>'
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    personalizer.personalize_tree(tree, "test.fr3")

    root = tree.getroot()
    memo = root.find(".//TfrxMemoView")
    assert memo.attrib["Text"] == "89073 Ulm"


def test_propdata_qr_code_personalization():
    from template_personalizer.fastreport_xml import FastReportXML

    cfg = PersonalizerConfig({
        "praxis": {
            "bic": "GENODEF1ULM",
            "iban": "DE02630901440012345678",
            "unternehmen": "Praxis Mustermann GbR",
        }
    })
    personalizer = TemplatePersonalizer(cfg)

    payload = (
        ' PresetClass="TfrxEPCPaymentPreset" '
        'DataObject.ServiceTag="BCD" '
        'DataObject.BIC="trim(&#60;praxis.&#34;bic&#34;&#62;)" '
        'DataObject.Name="&#60;praxis.&#34;unternehmen&#34;&#62;" '
        'DataObject.IBAN="trim(&#60;praxis.&#34;iban&#34;&#62;)" '
        'DataObject.Money.Amount="&#60;summe.&#34;brutto&#34;&#62;" '
        'DataObject.Information="\'Rechnungs Nr.\'+&#60;rechnung.&#34;rechnungnr&#34;&#62;"'
    )
    propdata_hex = FastReportXML.serialize_delphi_propdata([
        ("Formats", 0x0C, payload.encode("utf-8"))
    ])

    xml = (
        f'<TfrxReport Version="2025.1.7">'
        f'  <TfrxReportPage Name="Page1">'
        f'    <TfrxBarcode2DView Name="Barcode2D1" PropData="{propdata_hex}"/>'
        f'  </TfrxReportPage>'
        f'</TfrxReport>'
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    stats = personalizer.personalize_tree(tree, "test_qr.fr3")

    assert stats.files_modified == 1
    assert stats.replacements_per_field["praxis.bic"] == 1
    assert stats.replacements_per_field["praxis.iban"] == 1
    assert stats.replacements_per_field["praxis.unternehmen"] == 1

    root = tree.getroot()
    barcode = root.find(".//TfrxBarcode2DView")
    mod_props = FastReportXML.parse_delphi_propdata(barcode.attrib["PropData"])
    assert len(mod_props) == 1
    mod_text = mod_props[0][2].decode("utf-8")

    assert 'DataObject.BIC="\'GENODEF1ULM\'"' in mod_text
    assert 'DataObject.IBAN="\'DE02630901440012345678\'"' in mod_text
    assert 'DataObject.Name="\'Praxis Mustermann GbR\'"' in mod_text
    # Unrelated references preserved
    assert 'DataObject.Money.Amount="&#60;summe.&#34;brutto&#34;&#62;"' in mod_text
    assert 'DataObject.Information="\'Rechnungs Nr.\'+&#60;rechnung.&#34;rechnungnr&#34;&#62;"' in mod_text


def test_picture_view_logo_embedding(tmp_path):
    from template_personalizer.fastreport_xml import FastReportXML

    img_file = tmp_path / "test_logo.png"
    # Minimal 1x1 PNG bytes
    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15c4\x00\x00\x00\nIDATx\x9cc\x00\x01\x00"
        b"\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    img_file.write_bytes(png_bytes)

    cfg = PersonalizerConfig({
        "logo": {
            "filename": str(img_file),
        }
    })
    personalizer = TemplatePersonalizer(cfg)

    xml = (
        '<TfrxReport Version="2025.1.7">'
        '  <TfrxReportPage Name="Page1">'
        '    <TfrxPictureView Name="Picture1" Left="10" Top="10" Width="100" Height="100"/>'
        '  </TfrxReportPage>'
        '</TfrxReport>'
    )
    tree = ET.ElementTree(ET.fromstring(xml))
    stats = personalizer.personalize_tree(tree, "test_pic.fr3")

    assert stats.files_modified == 1
    assert stats.replacements_per_field["logo.image_embedded"] == 1

    root = tree.getroot()
    pic = root.find(".//TfrxPictureView")
    assert "Picture.PropData" in pic.attrib

    cls_name, extracted_bytes = FastReportXML.extract_picture_from_propdata(pic.attrib["Picture.PropData"])
    assert cls_name == "TPngImage"
    assert extracted_bytes == png_bytes


