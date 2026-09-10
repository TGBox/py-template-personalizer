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

    @staticmethod
    def parse_delphi_propdata(hex_str: str) -> list[tuple[str, int, bytes]]:
        """Parse a Delphi VCL binary property stream (hex-encoded) into a list of (prop_name, type_byte, payload_bytes)."""
        raw_bytes = bytes.fromhex(hex_str)
        pos = 0
        total_len = len(raw_bytes)
        properties: list[tuple[str, int, bytes]] = []

        while pos < total_len:
            prop_name_len = raw_bytes[pos]
            pos += 1
            prop_name = raw_bytes[pos : pos + prop_name_len].decode("latin-1", errors="replace")
            pos += prop_name_len
            type_byte = raw_bytes[pos]
            pos += 1

            if type_byte in (0x0C, 0x0A):  # vaLString (0x0C) or vaBinary (0x0A) -> 4-byte length
                length = int.from_bytes(raw_bytes[pos : pos + 4], "little")
                pos += 4
                payload = raw_bytes[pos : pos + length]
                pos += length
                properties.append((prop_name, type_byte, payload))
            elif type_byte == 0x06:  # vaString -> 1-byte length
                length = raw_bytes[pos]
                pos += 1
                payload = raw_bytes[pos : pos + length]
                pos += length
                properties.append((prop_name, type_byte, payload))
            else:
                # Store remainder as raw if unknown type
                rem = raw_bytes[pos - 2 - prop_name_len :]
                properties.append((prop_name, type_byte, rem))
                break

        return properties

    @staticmethod
    def serialize_delphi_propdata(properties: list[tuple[str, int, bytes]]) -> str:
        """Serialize a list of (prop_name, type_byte, payload_bytes) back into an uppercase hex string."""
        chunks = []
        for prop_name, type_byte, payload in properties:
            name_bytes = prop_name.encode("latin-1")
            name_len = len(name_bytes)
            if type_byte in (0x0C, 0x0A):
                chunk = (
                    bytes([name_len])
                    + name_bytes
                    + bytes([type_byte])
                    + len(payload).to_bytes(4, "little")
                    + payload
                )
            elif type_byte == 0x06:
                chunk = (
                    bytes([name_len])
                    + name_bytes
                    + bytes([type_byte])
                    + bytes([len(payload)])
                    + payload
                )
            else:
                chunk = payload
            chunks.append(chunk)

        return b"".join(chunks).hex().upper()

    @staticmethod
    def create_picture_propdata(image_bytes: bytes, file_ext: str = "") -> str:
        """Create FastReport Picture.PropData hex string for embedding an image."""
        if image_bytes.startswith(b"\xff\xd8"):
            cls_name = "TJPEGImage"
        elif image_bytes.startswith(b"\x89PNG"):
            cls_name = "TPngImage"
        elif image_bytes.startswith(b"BM"):
            cls_name = "TBitmap"
        elif image_bytes.startswith(b"GIF8"):
            cls_name = "TGIFImage"
        else:
            ext = file_ext.lower().lstrip(".")
            if ext in ("jpg", "jpeg"):
                cls_name = "TJPEGImage"
            elif ext == "png":
                cls_name = "TPngImage"
            elif ext == "bmp":
                cls_name = "TBitmap"
            elif ext == "gif":
                cls_name = "TGIFImage"
            else:
                cls_name = "TPngImage"

        cls_bytes = cls_name.encode("ascii")
        inner_payload = (
            bytes([len(cls_bytes)])
            + cls_bytes
            + len(image_bytes).to_bytes(4, "little")
            + image_bytes
        )
        total_bin_len = len(inner_payload)
        stream = (
            bytes([4])
            + b"Data"
            + bytes([0x0A])
            + total_bin_len.to_bytes(4, "little")
            + inner_payload
        )
        return stream.hex().upper()

    @staticmethod
    def extract_picture_from_propdata(hex_str: str) -> tuple[str, bytes]:
        """Extract (graphic_class_name, raw_image_bytes) from a Picture.PropData hex string."""
        raw = bytes.fromhex(hex_str)
        prop_len = raw[0]
        inner = raw[6 + prop_len :]
        cls_len = inner[0]
        cls_name = inner[1 : 1 + cls_len].decode("ascii", errors="replace")
        img_len = int.from_bytes(inner[1 + cls_len : 5 + cls_len], "little")
        img_bytes = inner[5 + cls_len : 5 + cls_len + img_len]
        return cls_name, img_bytes


