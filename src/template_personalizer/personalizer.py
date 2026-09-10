"""Core personalization engine for FastReport (.fr3) templates."""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

from .config import PersonalizerConfig, to_pascal_literal
from .fastreport_xml import FastReportXML

logger = logging.getLogger(__name__)


@dataclass
class ReplacementStats:
    """Tracks statistics about replacements made across files."""

    files_processed: int = 0
    files_modified: int = 0
    memos_unbound: int = 0
    replacements_per_field: Counter[str] = field(default_factory=Counter)
    replacements_per_file: Dict[str, int] = field(default_factory=dict)
    details: List[str] = field(default_factory=list)

    def merge(self, other: ReplacementStats) -> None:
        """Merge another stats instance into this one."""
        self.files_processed += other.files_processed
        self.files_modified += other.files_modified
        self.memos_unbound += other.memos_unbound
        self.replacements_per_field.update(other.replacements_per_field)
        for k, v in other.replacements_per_file.items():
            self.replacements_per_file[k] = self.replacements_per_file.get(k, 0) + v
        self.details.extend(other.details)

    @property
    def total_replacements(self) -> int:
        return sum(self.replacements_per_field.values())


class TemplatePersonalizer:
    """Transforms FastReport XML templates by replacing database field references with static values."""

    def __init__(self, config: PersonalizerConfig, verbose: bool = False):
        self.config = config
        self.verbose = verbose
        logo_info = self.config.get_logo_image_bytes()
        if logo_info:
            img_bytes, ext = logo_info
            self._logo_picture_propdata: Optional[str] = FastReportXML.create_picture_propdata(
                img_bytes, ext
            )
        else:
            self._logo_picture_propdata = None

    def personalize_tree(self, tree: ET.ElementTree, filename: str = "") -> ReplacementStats:
        """Apply personalization directly to an ElementTree in memory."""
        stats = ReplacementStats()
        stats.files_processed = 1
        root = tree.getroot()
        file_change_count = 0

        configured_tables = self.config.tables()
        if not configured_tables:
            return stats

        # 1. Replace PascalScript expressions in ScriptText.Text
        script_text = root.attrib.get("ScriptText.Text")
        if script_text:
            new_script, count, field_counts = self._replace_script_expressions(script_text)
            if count > 0:
                root.attrib["ScriptText.Text"] = new_script
                file_change_count += count
                stats.replacements_per_field.update(field_counts)
                stats.details.append(f"[{filename}] ScriptText: {count} references replaced")

        # 2. Iterate through all elements in the report
        for elem in root.iter():
            # Check script-like attributes (e.g. Highlight.Condition, Barcode Expression)
            for attr in ["Expression", "Highlight.Condition", "OnClick"]:
                if attr in elem.attrib:
                    val = elem.attrib[attr]
                    new_val, count, field_counts = self._replace_script_expressions(val)
                    if count > 0:
                        elem.attrib[attr] = new_val
                        file_change_count += count
                        stats.replacements_per_field.update(field_counts)
                        stats.details.append(
                            f"[{filename}] <{elem.tag} {attr}>: {count} references replaced"
                        )

            # Handle PropData attribute (e.g. TfrxBarcode2DView with DataObject)
            if "PropData" in elem.attrib:
                new_propdata, count = self._personalize_propdata(
                    elem.attrib["PropData"], filename, stats
                )
                if count > 0:
                    elem.attrib["PropData"] = new_propdata
                    file_change_count += count

            # Handle TfrxBarcode2DView
            if elem.tag == "TfrxBarcode2DView":
                expr = elem.attrib.get("Expression")
                if expr:
                    # Simplify trim('LITERAL') to 'LITERAL'
                    simplified = re.sub(
                        r"^trim\s*\(\s*('[^']*')\s*\)$", r"\1", expr, flags=re.IGNORECASE
                    )
                    if simplified != expr:
                        elem.attrib["Expression"] = simplified

            # Handle TfrxPictureView (embed logo image if configured and file exists)
            if elem.tag == "TfrxPictureView" and self._logo_picture_propdata:
                pic_name = elem.attrib.get("Name", "Picture")
                elem.attrib["Picture.PropData"] = self._logo_picture_propdata
                file_change_count += 1
                stats.replacements_per_field["logo.image_embedded"] += 1
                stats.details.append(
                    f"[{filename}] Picture '{pic_name}': Embedded logo image into Picture.PropData"
                )


            # Handle TfrxMemoView
            if elem.tag == "TfrxMemoView":
                memo_name = elem.attrib.get("Name", "UnnamedMemo")
                text = elem.attrib.get("Text")

                if text:
                    new_text, count, field_counts = self._replace_memo_text(text)
                    if count > 0:
                        elem.attrib["Text"] = new_text
                        file_change_count += count
                        stats.replacements_per_field.update(field_counts)
                        stats.details.append(
                            f"[{filename}] Memo '{memo_name}': {count} references replaced in Text"
                        )
                        text = new_text

                # Check and clean data binding attributes on TfrxMemoView
                unbound = self._clean_memo_bindings(elem, memo_name, filename, stats)
                if unbound:
                    file_change_count += 1

        if file_change_count > 0:
            stats.files_modified = 1
            stats.replacements_per_file[filename] = file_change_count

        return stats

    def _personalize_propdata(
        self, hex_str: str, filename: str, stats: ReplacementStats
    ) -> Tuple[str, int]:
        """Personalize embedded Delphi PropData property streams (e.g. Barcode2D DataObject)."""
        try:
            properties = FastReportXML.parse_delphi_propdata(hex_str)
        except Exception as e:
            logger.debug(f"Failed to parse PropData in {filename}: {e}")
            return hex_str, 0

        total_changes = 0
        mod_props = []

        def encode_propdata_attr(val: str) -> str:
            return val.replace("&", "&amp;").replace('"', "&#34;").replace("<", "&#60;").replace(">", "&#62;")

        for prop_name, type_byte, payload in properties:
            if type_byte == 0x0C and (prop_name == "Formats" or b"DataObject" in payload):
                text = payload.decode("utf-8", errors="replace")
                field_counts: Counter[str] = Counter()
                changes_here = 0

                # 1. Replace trim(...) wrapped references, simplifying to plain literal
                pattern_trim = re.compile(
                    r'trim\s*\(\s*(?:<|&#60;)([a-zA-Z0-9_]+)\.(?:"|&#34;)?([a-zA-Z0-9_]+)(?:"|&#34;)?(?:>|&#62;)\s*\)',
                    re.IGNORECASE,
                )

                def repl_trim(match: re.Match) -> str:
                    nonlocal changes_here
                    tbl = match.group(1).lower()
                    fld = match.group(2).lower()
                    if self.config.has_field(tbl, fld):
                        changes_here += 1
                        field_counts[f"{tbl}.{fld}"] += 1
                        lit = self.config.get_pascal_literal(tbl, fld)
                        return encode_propdata_attr(lit)  # type: ignore
                    return match.group(0)

                text = pattern_trim.sub(repl_trim, text)

                # 2. Replace simple angle bracket references
                pattern_simple = re.compile(
                    r'(?:<|&#60;)([a-zA-Z0-9_]+)\.(?:"|&#34;)?([a-zA-Z0-9_]+)(?:"|&#34;)?(?:>|&#62;)',
                    re.IGNORECASE,
                )

                def repl_simple(match: re.Match) -> str:
                    nonlocal changes_here
                    tbl = match.group(1).lower()
                    fld = match.group(2).lower()
                    if self.config.has_field(tbl, fld):
                        changes_here += 1
                        field_counts[f"{tbl}.{fld}"] += 1
                        lit = self.config.get_pascal_literal(tbl, fld)
                        return encode_propdata_attr(lit)  # type: ignore
                    return match.group(0)

                text = pattern_simple.sub(repl_simple, text)

                if changes_here > 0:
                    total_changes += changes_here
                    stats.replacements_per_field.update(field_counts)
                    stats.details.append(
                        f"[{filename}] PropData '{prop_name}': {changes_here} references replaced in DataObject"
                    )
                    payload = text.encode("utf-8")

            mod_props.append((prop_name, type_byte, payload))

        if total_changes > 0:
            return FastReportXML.serialize_delphi_propdata(mod_props), total_changes
        return hex_str, 0


    def _replace_script_expressions(self, text: str) -> Tuple[str, int, Counter[str]]:
        """Replace <table."field"> or <table.field> references in PascalScript code with string literals."""
        total_count = 0
        field_counts: Counter[str] = Counter()

        def repl(match: re.Match) -> str:
            nonlocal total_count
            tbl = match.group(1).lower()
            fld = match.group(2).lower()
            if self.config.has_field(tbl, fld):
                total_count += 1
                field_counts[f"{tbl}.{fld}"] += 1
                return self.config.get_pascal_literal(tbl, fld)  # type: ignore
            return match.group(0)

        # Regex matches <table."field"> or <table.field>
        pattern = re.compile(r'<([a-zA-Z0-9_]+)\.(?:"|&#34;)?([a-zA-Z0-9_]+)(?:"|&#34;)?>', re.IGNORECASE)
        result = pattern.sub(repl, text)
        return result, total_count, field_counts

    def _replace_memo_text(self, text: str) -> Tuple[str, int, Counter[str]]:
        """Replace both angle bracket (<tbl."fld">) and square bracket ([tbl."fld"]) references in memo text."""
        total_count = 0
        field_counts: Counter[str] = Counter()

        # Step A: Replace angle bracket expressions (<tbl."fld">) with PascalScript literals
        def repl_angle(match: re.Match) -> str:
            nonlocal total_count
            tbl = match.group(1).lower()
            fld = match.group(2).lower()
            if self.config.has_field(tbl, fld):
                total_count += 1
                field_counts[f"{tbl}.{fld}"] += 1
                return self.config.get_pascal_literal(tbl, fld)  # type: ignore
            return match.group(0)

        pattern_angle = re.compile(r'<([a-zA-Z0-9_]+)\.(?:"|&#34;)?([a-zA-Z0-9_]+)(?:"|&#34;)?>', re.IGNORECASE)
        text = pattern_angle.sub(repl_angle, text)

        # Step B: Replace square bracket placeholders ([tbl."fld"]) with raw static string values
        def repl_sq(match: re.Match) -> str:
            nonlocal total_count
            tbl = match.group(1).lower()
            fld = match.group(2).lower()
            if self.config.has_field(tbl, fld):
                total_count += 1
                field_counts[f"{tbl}.{fld}"] += 1
                return self.config.get_value(tbl, fld)  # type: ignore
            return match.group(0)

        pattern_sq = re.compile(r'\[([a-zA-Z0-9_]+)\.(?:"|&#34;)?([a-zA-Z0-9_]+)(?:"|&#34;)?\]', re.IGNORECASE)
        text = pattern_sq.sub(repl_sq, text)

        # Step C: Simplify pure string concatenations in brackets (e.g. ['89073'+' '+'Ulm'] -> 89073 Ulm)
        def simplify_concat(match: re.Match) -> str:
            expr = match.group(1).strip()
            parts = re.findall(r"'([^']*)'", expr)
            test = expr
            for p in parts:
                test = test.replace(f"'{p}'", "", 1)
            test = test.replace("+", "").strip()
            if test == "" and parts:
                return "".join(parts)
            return match.group(0)

        text = re.sub(r'\[([^\]]*\+[^\]]*)\]', simplify_concat, text)

        return text, total_count, field_counts

    def _clean_memo_bindings(
        self, elem: ET.Element, memo_name: str, filename: str, stats: ReplacementStats
    ) -> bool:
        """Remove DataSet, DataSetName, and DataField from TfrxMemoView if all fields are resolved."""
        ds_raw = elem.attrib.get("DataSet") or elem.attrib.get("DataSetName")
        if not ds_raw:
            return False

        ds_lower = ds_raw.strip().lower()
        if ds_lower not in self.config.tables():
            return False

        current_text = elem.attrib.get("Text", "")
        # Check if any unresolved references to this dataset remain in Text
        unresolved = re.search(
            rf'\[{re.escape(ds_lower)}\.|\<{re.escape(ds_lower)}\.', current_text, re.IGNORECASE
        )
        if unresolved:
            return False

        # All references to this dataset in this memo were personalized or none were present
        data_field = elem.attrib.get("DataField")
        elem.attrib.pop("DataSet", None)
        elem.attrib.pop("DataSetName", None)
        elem.attrib.pop("DataField", None)

        # Also remove Formats child if no bracket expressions remain
        formats = elem.find("Formats")
        if formats is not None and not re.search(r'\[.*?\]', current_text):
            elem.remove(formats)

        stats.memos_unbound += 1
        stats.details.append(
            f"[{filename}] Memo '{memo_name}': Unbound from dataset '{ds_raw}' (DataField='{data_field}')"
        )
        return True

    def personalize_file(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        in_place: bool = False,
        dry_run: bool = False,
    ) -> ReplacementStats:
        """Personalize a single .fr3 template file."""
        inp = Path(input_path)
        if not inp.is_file():
            raise FileNotFoundError(f"Input file not found: {inp}")

        tree = FastReportXML.parse_file(inp)
        stats = self.personalize_tree(tree, filename=inp.name)

        if dry_run:
            logger.info(f"[DRY-RUN] Processed {inp.name} ({stats.total_replacements} replacements)")
            return stats

        dest = inp if in_place else Path(output_path or inp)
        FastReportXML.save_file(tree.getroot(), dest)
        logger.info(f"Saved personalized template to {dest}")
        return stats

    def personalize_directory(
        self,
        input_dir: Union[str, Path],
        output_dir: Optional[Union[str, Path]] = None,
        pattern: str = "*.fr3",
        in_place: bool = False,
        dry_run: bool = False,
    ) -> ReplacementStats:
        """Personalize all matching templates in a directory."""
        inp_dir = Path(input_dir)
        if not inp_dir.is_dir():
            raise NotADirectoryError(f"Input directory not found: {inp_dir}")

        files = sorted(list(inp_dir.glob(pattern)))
        combined_stats = ReplacementStats()

        out_dir = Path(output_dir) if output_dir else None
        if out_dir and not in_place and not dry_run:
            out_dir.mkdir(parents=True, exist_ok=True)

        for file_path in files:
            dest_path = out_dir / file_path.name if out_dir and not in_place else None
            file_stats = self.personalize_file(
                file_path, output_path=dest_path, in_place=in_place, dry_run=dry_run
            )
            combined_stats.merge(file_stats)

        return combined_stats
