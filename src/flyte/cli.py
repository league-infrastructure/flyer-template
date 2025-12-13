from __future__ import annotations

import argparse
import sys
from pathlib import Path

from flyte.flyte import Flyte


def cmd_import(args: argparse.Namespace) -> None:
    """Handle the import subcommand."""
    src = Path(args.source)
    out_dir = Path(args.output) if args.output else None
    app = Flyte(data_dir=Path.cwd())
    result = app.import_template(
        src,
        output_dir=out_dir,
        placeholder_color=args.color,
        tolerance=args.tolerance,
        edge_dilation=args.dilate,
        background_sample_offset=args.offset,
        label_font=args.label_font,
        replace=args.replace,
    )
    print(str(result["template"]))
    print(str(result["reference"]))
    print(str(result["regions"]))


def cmd_compile(args: argparse.Namespace) -> None:
    """Handle the compile subcommand."""
    content_file = Path(args.content)
    template_dir = Path(args.template_dir)
    
    # Handle output: if it's a directory, construct filename from template name
    if args.output:
        output = Path(args.output)
        if output.is_dir() or (not output.suffix and not output.exists()):
            # It's a directory - construct filename from template directory name
            template_name = template_dir.name
            output = output / f"{template_name}.html"
    else:
        output = Path("output.html")
    
    style = Path(args.style) if args.style else None
    
    app = Flyte(data_dir=Path.cwd())
    result = app.compile(
        content_file,
        template_dir,
        output,
        style=style,
    )
    print(str(result))


def cmd_render(args: argparse.Namespace) -> None:
    """Handle the render subcommand."""
    html_file = Path(args.html)
    
    # Handle output: if it's a directory, construct filename from HTML name
    if args.output:
        output = Path(args.output)
        if output.is_dir() or (not output.suffix and not output.exists()):
            # It's a directory - construct filename from HTML file name
            html_stem = html_file.stem
            # Default to PNG if no format specified
            ext = ".png" if not args.format else f".{args.format}"
            output = output / f"{html_stem}{ext}"
        elif args.format:
            # If format is specified but output has extension, use the format
            output = output.with_suffix(f".{args.format}")
    else:
        # No output specified, use HTML filename with .png/.pdf extension
        ext = ".png" if not args.format else f".{args.format}"
        output = html_file.with_suffix(ext)
    
    app = Flyte(data_dir=Path.cwd())
    result = app.render_html(html_file, output)
    print(str(result))


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
        help="Output directory (default: same directory as source file)",
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
    import_parser.add_argument(
        "-r",
        "--replace",
        dest="replace",
        action="store_true",
        help="Replace existing regions.yaml (default: preserve region names if positions match)",
    )
    import_parser.set_defaults(func=cmd_import)
    
    # Compile subcommand
    compile_parser = subparsers.add_parser(
        "compile",
        help="Compile content and template into HTML",
    )
    compile_parser.add_argument(
        "content",
        metavar="CONTENT",
        help="Content YAML file",
    )
    compile_parser.add_argument(
        "template_dir",
        metavar="TEMPLATE_DIR",
        help="Template directory containing regions.yaml and template.png",
    )
    compile_parser.add_argument(
        "-o",
        "--output",
        dest="output",
        metavar="OUTPUT",
        help="Output HTML file (default: output.html)",
    )
    compile_parser.add_argument(
        "-s",
        "--style",
        dest="style",
        metavar="STYLE",
        help="Optional CSS stylesheet file",
    )
    compile_parser.set_defaults(func=cmd_compile)
    
    # Render subcommand
    render_parser = subparsers.add_parser(
        "render",
        help="Render HTML to PNG or PDF",
    )
    render_parser.add_argument(
        "html",
        metavar="HTML",
        help="HTML file to render",
    )
    render_parser.add_argument(
        "-o",
        "--output",
        dest="output",
        metavar="OUTPUT",
        help="Output PNG or PDF file (default: same name as HTML with .png extension)",
    )
    render_parser.add_argument(
        "-f",
        "--format",
        dest="format",
        choices=["png", "pdf"],
        help="Output format (png or pdf). If not specified, determined by output extension or defaults to png",
    )
    render_parser.set_defaults(func=cmd_render)
    
    args = parser.parse_args(argv)
    
    try:
        args.func(args)
    except Exception as e:
        print(f"flyte: error: {e}", file=sys.stderr)
        raise SystemExit(2)
