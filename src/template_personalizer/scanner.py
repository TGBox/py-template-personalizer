"""Scanner module for analyzing FastReport templates and discovering field references."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Union


class TemplateScanner:
    """Scans .fr3 files to discover referenced datasets, fields, queries, and variables."""

    @staticmethod
    def scan_file(file_path: Union[str, Path]) -> Dict[str, Set[str]]:
        """Scan a single template file and return a dict of table_name -> set of field_names."""
        path = Path(file_path)
        tables_fields: Dict[str, Set[str]] = defaultdict(set)

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            tree = ET.fromstring(content)
        except Exception:
            return tables_fields

        # 1. Check all attributes of all elements
        for elem in tree.iter():
            for attr_name, attr_val in elem.attrib.items():
                if not attr_val:
                    continue
                # Match [table."field"] or [table.field]
                matches_sq = re.findall(
                    r'\[([a-zA-Z0-9_]+)\.(?:"|&#34;)?([a-zA-Z0-9_]+)(?:"|&#34;)?\]', attr_val
                )
                for tbl, fld in matches_sq:
                    tables_fields[tbl.lower()].add(fld.lower())

                # Match <table."field"> or <table.field>
                matches_ang = re.findall(
                    r'<([a-zA-Z0-9_]+)\.(?:"|&#34;)?([a-zA-Z0-9_]+)(?:"|&#34;)?>', attr_val
                )
                for tbl, fld in matches_ang:
                    tables_fields[tbl.lower()].add(fld.lower())

            # Check DataField and DataSet
            if elem.tag == "TfrxMemoView":
                ds = elem.attrib.get("DataSet") or elem.attrib.get("DataSetName")
                df = elem.attrib.get("DataField")
                if ds and df:
                    tables_fields[ds.lower()].add(df.lower())

            # Check PropData (e.g. Barcode2D DataObject)
            if "PropData" in elem.attrib:
                try:
                    from .fastreport_xml import FastReportXML

                    props = FastReportXML.parse_delphi_propdata(elem.attrib["PropData"])
                    for _, t_byte, payload in props:
                        if t_byte == 0x0C:
                            payload_text = payload.decode("utf-8", errors="replace")
                            matches_ang_pd = re.findall(
                                r'(?:<|&#60;)([a-zA-Z0-9_]+)\.(?:"|&#34;)?([a-zA-Z0-9_]+)(?:"|&#34;)?(?:>|&#62;)',
                                payload_text,
                            )
                            for tbl, fld in matches_ang_pd:
                                tables_fields[tbl.lower()].add(fld.lower())
                except Exception:
                    pass

        return tables_fields

    @classmethod
    def scan_directory(
        cls, dir_path: Union[str, Path], pattern: str = "*.fr3"
    ) -> Dict[str, List[str]]:
        """Scan all matching files in a directory and return sorted tables and fields."""
        path = Path(dir_path)
        combined: Dict[str, Set[str]] = defaultdict(set)

        for f in path.glob(pattern):
            file_results = cls.scan_file(f)
            for tbl, flds in file_results.items():
                combined[tbl].update(flds)

        return {tbl: sorted(list(flds)) for tbl, flds in sorted(combined.items())}

    @classmethod
    def generate_config_template(
        cls, dir_path: Union[str, Path], focus_tables: tuple[str, ...] = ("praxis", "logo")
    ) -> Dict[str, Dict[str, str]]:
        """Generate a dictionary template suitable for exporting as YAML or JSON config."""
        discovered = cls.scan_directory(dir_path)
        result: Dict[str, Dict[str, str]] = {}

        for tbl in focus_tables:
            tbl_lower = tbl.lower()
            if tbl_lower in discovered:
                result[tbl_lower] = {fld: "" for fld in discovered[tbl_lower]}
            else:
                result[tbl_lower] = {}

        return result
