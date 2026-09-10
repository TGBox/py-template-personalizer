import xml.etree.ElementTree as ET
from template_personalizer.fastreport_xml import FastReportXML


def test_encode_attribute():
    assert FastReportXML.encode_attribute("Hello") == "Hello"
    assert FastReportXML.encode_attribute('Quotes: "Hi"') == 'Quotes: &#34;Hi&#34;'
    assert FastReportXML.encode_attribute("Line1\r\nLine2") == "Line1&#13;&#10;Line2"
    assert FastReportXML.encode_attribute("<expr>") == "&#60;expr&#62;"
    assert FastReportXML.encode_attribute("A & B") == "A &amp; B"


def test_serialize_fastreport_xml():
    root = ET.Element("TfrxReport", {"Version": "2025.1.7", "ScriptText.Text": "begin\r\nend."})
    child = ET.SubElement(root, "TfrxDataPage", {"Name": "Data"})
    memo = ET.SubElement(child, "TfrxMemoView", {"Name": "Memo1", "Text": 'Line1\r\nLine2: "val"'})

    xml_str = FastReportXML.serialize(root)

    assert xml_str.startswith('<?xml version="1.0" encoding="utf-8" standalone="no"?>')
    assert '&#13;&#10;' in xml_str
    assert '&#34;val&#34;' in xml_str
    assert xml_str.endswith("\r\n")

    # Verify ElementTree can parse back identically
    roundtrip = ET.fromstring(xml_str)
    assert roundtrip.tag == "TfrxReport"
    assert roundtrip.attrib["Version"] == "2025.1.7"
    assert roundtrip.attrib["ScriptText.Text"] == "begin\r\nend."
    memo_roundtrip = roundtrip.find(".//TfrxMemoView")
    assert memo_roundtrip is not None
    assert memo_roundtrip.attrib["Text"] == 'Line1\r\nLine2: "val"'
