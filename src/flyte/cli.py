from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flyte.flyte import Flyte


def cmd_import(args: argparse.Namespace) -> None:
    """Handle the import subcommand."""
    src = Path(args.source)
    out_dir = Path(args.output)
    app = Flyte(data_dir=Path.cwd())
    result = app.import_template(
        src,
        output_dir=out_dir,
        placeholder_color=args.color,
        tolerance=args.tolerance,
        edge_dilation=args.dilate,
        background_sample_offset=args.offset,
        label_font=args.label_font,
    )
    print(str(result["template"]))
    print(str(result["reference"]))
    print(str(result["regions"]))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="flyte",
        description="Flyer template rendering system",
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")
    
    # Import subcommand
    import_parser = subparsers.add_parser(
        "import",
        help="Import a source template image and generate template/reference/YAML",
    )
    import_parser.add_argument(
        "source",
        metavar="SOURCE",
        help="Source template image file",
    )
    import_parser.add_argument(
        "-o",
        "--output",
        dest="output",
        metavar="OUTPUT",
        required=True,
        help="Output directory",
    )
    import_parser.add_argument(
        "--color",
        default="#6fe600",
        help="Placeholder hex color (default: #6fe600)",
    )
    import_parser.add_argument(
        "--tolerance",
        type=int,
        default=20,
        help="Color tolerance 0-255 (default: 20)",
    )
    import_parser.add_argument(
        "--dilate",
        type=int,
        default=5,
        help="Mask dilation kernel size in pixels (default: 5)",
    )
    import_parser.add_argument(
        "--offset",
        type=int,
        default=5,
        help="Background sample offset from region edge (default: 5)",
    )
    import_parser.add_argument(
        "--label-font",
        dest="label_font",
        metavar="FONT_PATH",
        help="Optional TrueType/OTF font path to use for reference labels",
    )
    import_parser.set_defaults(func=cmd_import)
    
    args = parser.parse_args(argv)
    
    try:
        args.func(args)
    except Exception as e:
        print(f"flyte: error: {e}", file=sys.stderr)
        raise SystemExit(2)
