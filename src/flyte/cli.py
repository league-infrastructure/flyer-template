from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flyte.flyte import Flyte


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="flyte")

    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument(
        "-i",
        "--import",
        dest="source_image",
        metavar="SOURCE",
        help="Import a source template image and generate template/reference/YAML.",
    )
    mode.add_argument(
        "-r",
        "--regions",
        dest="regions_file",
        metavar="REGIONS",
        help="Render a template using a regions YAML file.",
    )

    parser.add_argument(
        "-o",
        "--output",
        dest="output",
        metavar="OUTPUT",
        required=True,
        help="Output directory (for -i) or output image path (for -r).",
    )

    # import/analyze options
    parser.add_argument("--color", default="#6fe600", help="Placeholder hex color (default: #6fe600).")
    parser.add_argument("--tolerance", type=int, default=20, help="Color tolerance 0-255 (default: 20).")
    parser.add_argument(
        "--dilate",
        type=int,
        default=5,
        help="Mask dilation kernel size in pixels (default: 5).",
    )
    parser.add_argument(
        "--offset",
        type=int,
        default=5,
        help="Background sample offset from region edge (default: 5).",
    )
    parser.add_argument(
        "--label-font",
        dest="label_font",
        metavar="FONT_PATH",
        help="Optional TrueType/OTF font path to use for reference labels.",
    )

    # render options
    parser.add_argument(
        "-c",
        "--content",
        dest="content_file",
        metavar="CONTENT",
        help="Content YAML/JSON mapping region name/id -> HTML (required with -r).",
    )
    parser.add_argument(
        "--css-dir",
        dest="css_dir",
        metavar="CSS_DIR",
        help="Optional directory to resolve CSS paths listed in regions YAML.",
    )

    args = parser.parse_args(argv)

    try:
        if args.source_image:
            src = Path(args.source_image)
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
            return

        if not args.content_file:
            raise ValueError("-c/--content is required with -r/--regions")

        regions_path = Path(args.regions_file)
        content_path = Path(args.content_file)
        out_path = Path(args.output)
        app = Flyte(data_dir=Path.cwd(), css_dir=Path(args.css_dir) if args.css_dir else None)
        rendered = app.render(regions_path, content_path, out_path)
        print(str(rendered))
    except Exception as e:
        print(f"flyte: error: {e}", file=sys.stderr)
        raise SystemExit(2)
