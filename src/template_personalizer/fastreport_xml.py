"""FastReport (.fr3) XML reader and serializer.

Ensures that FastReport XML conventions (XML declaration, entity encoding of newlines,
quotes, brackets, and element indentation) are faithfully preserved.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Union


class FastReportXML:
    """Helper for reading, manipulating, and writing FastReport XML documents."""

    @staticmethod
    def parse_file(file_path: Union[str, Path]) -> ET.ElementTree:
        """Parse an .fr3 file into an ElementTree."""
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return ET.ElementTree(ET.fromstring(content))

    @staticmethod
    def parse_string(xml_text: str) -> ET.ElementTree:
        """Parse an XML string into an ElementTree."""
        return ET.ElementTree(ET.fromstring(xml_text))

    @staticmethod
    def serialize(root: ET.Element, indent: int = 2) -> str:
        """Serialize an ElementTree root element to a FastReport-compatible XML string."""
        lines = ['<?xml version="1.0" encoding="utf-8" standalone="no"?>']

        def _serialize_node(elem: ET.Element, level: int) -> None:
            pad = " " * (level * indent)
            attr_str = ""
            for k, v in elem.attrib.items():
                attr_str += f' {k}="{FastReportXML.encode_attribute(v)}"'

            children = list(elem)
            has_text = elem.text and elem.text.strip()

            if not children and not has_text:
                lines.append(f"{pad}<{elem.tag}{attr_str}/>")
            else:
                lines.append(f"{pad}<{elem.tag}{attr_str}>")
                if has_text:
                    t_pad = " " * ((level + 1) * indent)
                    lines.append(f"{t_pad}{elem.text.strip()}")
                for child in children:
                    _serialize_node(child, level + 1)
                lines.append(f"{pad}</{elem.tag}>")

        _serialize_node(root, 0)
        lines.append("")  # Trailing newline
        return "\r\n".join(lines)

    @staticmethod
    def save_file(root: ET.Element, file_path: Union[str, Path], indent: int = 2) -> None:
        """Serialize and save to a file using UTF-8 encoding and CRLF line endings."""
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        xml_content = FastReportXML.serialize(root, indent=indent)
        with open(path, "w", encoding="utf-8", newline="") as f:
            f.write(xml_content)

    @staticmethod
    def encode_attribute(val: Union[str, int, float, bool]) -> str:
        """Encode an attribute value matching FastReport VCL XML entity rules."""
        if not isinstance(val, str):
            val = str(val)
        # 1. Ampersand
        s = val.replace("&", "&amp;")
        # 2. Quotes
        s = s.replace('"', "&#34;")
        # 3. Newlines (CRLF)
        s = s.replace("\r\n", "&#13;&#10;").replace("\r", "&#13;").replace("\n", "&#10;")
        # 4. Angle brackets
        s = s.replace("<", "&#60;").replace(">", "&#62;")
        return s
