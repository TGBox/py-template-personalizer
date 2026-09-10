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
    assert barcode.attrib["Expression"] == "trim('DE12345678')"

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
