"""Command Line Interface for py-template-personalizer."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Sequence

from .config import load_config
from .personalizer import TemplatePersonalizer
from .scanner import TemplateScanner


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="template-personalizer",
        description="Personalize FastReport (.fr3) templates by replacing database field references with configured static values.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        default=None,
        help="Path to YAML or JSON configuration file (default: config.yaml or config.json).",
    )
    parser.add_argument(
        "-i",
        "--input-dir",
        type=Path,
        default=Path("testdata"),
        help="Directory containing source .fr3 template files (default: testdata).",
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Directory where personalized templates are saved (default: output).",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite template files directly in the input directory (warning: mutates source files!).",
    )
    parser.add_argument(
        "-d",
        "--dry-run",
        action="store_true",
        help="Preview changes without writing any modified files.",
    )
    parser.add_argument(
        "-p",
        "--pattern",
        type=str,
        default="*.fr3",
        help="File pattern to match in input directory (default: *.fr3).",
    )
    parser.add_argument(
        "--generate-config",
        type=Path,
        nargs="?",
        const=Path("config.generated.yaml"),
        default=None,
        metavar="OUTPUT_PATH",
        help="Scan input templates and generate an empty configuration template (default: config.generated.yaml).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Display detailed per-memo and per-script modification messages.",
    )

    return parser


def find_default_config() -> Optional[Path]:
    """Look for standard config file locations."""
    for candidate in [
        Path("config.yaml"),
        Path("config.yml"),
        Path("config.json"),
        Path("config.example.yaml"),
        Path("config.example.json"),
    ]:
        if candidate.is_file():
            return candidate
    return None


def print_banner() -> None:
    print("=" * 70)
    print(" FastReport (.fr3) Template Personalizer")
    print("=" * 70)


def main(args: Optional[Sequence[str]] = None) -> int:
    parser = create_parser()
    opts = parser.parse_args(args)

    # Configure logging
    log_level = logging.DEBUG if opts.verbose else logging.INFO
    logging.basicConfig(level=log_level, format="%(levelname)s: %(message)s")

    print_banner()

    # Mode: Generate Config Template
    if opts.generate_config is not None:
        target_path = opts.generate_config
        input_dir = opts.input_dir
        if not input_dir.is_dir():
            print(f"Error: Input directory not found: {input_dir}", file=sys.stderr)
            return 1

        print(f"Scanning templates in '{input_dir}' to generate config template...")
        tpl = TemplateScanner.generate_config_template(input_dir)

        # Format output as YAML if pyyaml is available, otherwise JSON
        ext = target_path.suffix.lower()
        if ext in (".yaml", ".yml") or ext == "":
            try:
                import yaml

                content = yaml.dump(tpl, sort_keys=False, allow_unicode=True)
            except ImportError:
                import json

                content = json.dumps(tpl, indent=2, ensure_ascii=False)
        else:
            import json

            content = json.dumps(tpl, indent=2, ensure_ascii=False)

        target_path.write_text(content, encoding="utf-8")
        print(f"Configuration template written to: {target_path}")
        return 0

    # Locate config file
    config_path = opts.config or find_default_config()
    if not config_path or not config_path.is_file():
        print(
            "Error: No configuration file specified or found. Provide one via --config <path> "
            "or generate one with --generate-config.",
            file=sys.stderr,
        )
        return 1

    print(f"Loading configuration: {config_path}")
    try:
        config = load_config(config_path)
    except Exception as e:
        print(f"Error loading configuration: {e}", file=sys.stderr)
        return 1

    print(f"Configured tables: {', '.join(config.tables())}")
    for tbl in config.tables():
        print(f"  [{tbl}]: {len(config.fields_for_table(tbl))} fields configured")

    input_dir = opts.input_dir
    if not input_dir.is_dir():
        print(f"Error: Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    if opts.dry_run:
        print("\n>>> DRY RUN MODE (No files will be modified or created) <<<\n")
    elif opts.in_place:
        print(f"\n>>> IN-PLACE MODE: Modifying files directly in '{input_dir}' <<<\n")
    else:
        print(f"\nOutput directory: '{opts.output_dir}'")

    personalizer = TemplatePersonalizer(config, verbose=opts.verbose)
    stats = personalizer.personalize_directory(
        input_dir=input_dir,
        output_dir=opts.output_dir,
        pattern=opts.pattern,
        in_place=opts.in_place,
        dry_run=opts.dry_run,
    )

    # Print Summary Report
    print("\n" + "=" * 70)
    print(" Summary Report")
    print("=" * 70)
    print(f"  Files scanned:       {stats.files_processed}")
    print(f"  Files modified:      {stats.files_modified}")
    print(f"  Total replacements:  {stats.total_replacements}")
    print(f"  Memos unbound:       {stats.memos_unbound} (live DB bindings cleared)")

    if stats.replacements_per_field:
        print("\n  Replacements by field:")
        for fld, count in stats.replacements_per_field.most_common():
            print(f"    - {fld:<25}: {count:>4}x")

    if opts.verbose and stats.details:
        print("\n  Detailed modifications:")
        for detail in stats.details[:50]:
            print(f"    * {detail}")
        if len(stats.details) > 50:
            print(f"    ... and {len(stats.details) - 50} more details.")

    print("=" * 70)
    if opts.dry_run:
        print("Dry run completed successfully. No changes written.")
    else:
        dest_desc = input_dir if opts.in_place else opts.output_dir
        print(f"Personalization complete! Modified files saved to: {dest_desc}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
