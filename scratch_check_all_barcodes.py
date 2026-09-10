import os
from pathlib import Path
import xml.etree.ElementTree as ET

for p in Path("testdata").glob("*.fr3"):
    try:
        tree = ET.parse(p)
        for el in tree.iter():
            prop_data = el.get("PropData")
            if prop_data:
                try:
                    raw = bytes.fromhex(prop_data)
                    text = raw.decode("latin-1", errors="replace")
                    if "praxis" in text.lower() or "DataObject" in text:
                        print(f"File: {p.name}")
                        print(f"  Tag: {el.tag}, Name: {el.get('Name')}")
                        print(f"  Prefix bytes: {repr(raw[:15])}")
                        print(f"  Text: {text}")
                        print("-" * 50)
                except Exception as e:
                    pass
            expr = el.get("Expression")
            if expr and "praxis" in expr.lower():
                print(f"File: {p.name} Expression: {expr}")
    except Exception as e:
        print(f"Error parsing {p}: {e}")
