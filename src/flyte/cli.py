from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

from flyte.flyte import Flyte
import textwrap
from jinja2 import Environment, FileSystemLoader, select_autoescape
try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None

__version__ = "0.1.1"


def cmd_import(args: argparse.Namespace) -> None:
    """Handle the import subcommand."""
    src = Path(args.source)
    out_dir = Path(args.output) if args.output else None
    repo_url = args.repo_url if hasattr(args, 'repo_url') else None
    app = Flyte(data_dir=Path.cwd())
    
    # Check if source is a directory
    if src.is_dir():
        # Import all image files in the directory
        image_extensions = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.webp', '.pdf'}
        image_files = []
        
        # Recursively find all image files
        for ext in image_extensions:
            image_files.extend(src.rglob(f'*{ext}'))
            image_files.extend(src.rglob(f'*{ext.upper()}'))
        
        if not image_files:
            print(f"No image files found in {src}", file=sys.stderr)
            sys.exit(1)
        
        print(f"Found {len(image_files)} image file(s) to import:")
        for img_file in sorted(image_files):
            relative_path = img_file.relative_to(src)
            print(f"  {relative_path}")
        print()
        
        # Track all imported templates for index
        templates_index = []
        
        # Import each file
        for img_file in sorted(image_files):
            # Calculate relative path from source directory
            relative_path = img_file.relative_to(src)
            
            # Determine output directory preserving structure
            if out_dir:
                # Use the relative directory structure in output
                file_output_dir = out_dir / relative_path.parent
            else:
                # Use source file's parent directory (default behavior)
                file_output_dir = img_file.parent
            
            print(f"Importing: {relative_path}")
            result = app.import_template(
                img_file,
                output_dir=file_output_dir,
                placeholder_color=args.color,
                tolerance=args.tolerance,
                edge_dilation=args.dilate,
                background_sample_offset=args.offset,
                label_font=args.label_font,
                replace=args.replace,
            )
            print(f"  → {result['template']}")
            print(f"  → {result['reference']}")
            print(f"  → {result['regions']}")
            print()
            
            # Add to index: determine the template directory path relative to output
            template_dir = Path(result['regions']).parent
            if out_dir:
                # Resolve both to absolute paths before computing relative path
                relative_template_path = template_dir.resolve().relative_to(out_dir.resolve())
            else:
                # When no output dir specified, templates are created alongside source files
                # Use the path relative to the source directory itself
                relative_template_path = template_dir.resolve().relative_to(src.resolve())
            
            templates_index.append(str(relative_template_path))
        
        # Write index.json in the output directory
        if out_dir:
            index_path = out_dir / "index.json"
        else:
            # When no output dir, write index to source directory
            index_path = src / "index.json"
        
        index_data = {
            "templates": templates_index,
            "count": len(templates_index)
        }
        
        if repo_url:
            index_data["repo_url"] = repo_url
            # Extract source directory path for upload links
            index_data["source_path"] = "source"
        
        with index_path.open('w', encoding='utf-8') as f:
            json.dump(index_data, f, indent=2)
        
        print(f"Created index: {index_path}")
        
        # Copy index.html template to output directory
        template_dir = Path(__file__).parent / "templates"
        index_html_template = template_dir / "index.html"
        
        if out_dir:
            index_html_dest = out_dir / "index.html"
        else:
            index_html_dest = src / "index.html"
        
        if index_html_template.exists():
            shutil.copy2(index_html_template, index_html_dest)
            print(f"Created gallery: {index_html_dest}")
        else:
            print(f"Warning: Template not found at {index_html_template}", file=sys.stderr)

        # Generate fonts.html from docs/fonts.yaml if available (via Jinja2 template)
        try:
            fonts_yaml_path = Path("docs/fonts.yaml")
            if yaml is None:
                raise RuntimeError("PyYAML not installed; cannot render fonts.html")
            if fonts_yaml_path.exists():
                with fonts_yaml_path.open("r", encoding="utf-8") as f:
                    fonts_data = yaml.safe_load(f) or {}

                def as_list(value):
                    return [x for x in (value or []) if isinstance(x, str)]

                main = as_list(fonts_data.get("main"))
                main_nogoogle = as_list(fonts_data.get("main_nogoogle")) or as_list(fonts_data.get("nogoogle"))
                other = as_list(fonts_data.get("other"))
                # If category-based structure (arbitrary keys -> list) is provided, capture it
                category_sections: list[tuple[str, list[str]]] = []
                if not (main or main_nogoogle or other):
                    for k, v in fonts_data.items():
                        if isinstance(v, list) and all(isinstance(x, str) for x in v):
                            title = k.replace("_", " ").title()
                            category_sections.append((title, [str(x) for x in v]))

                # Build Google Fonts links to ensure samples render with intended families
                fam_set: set[str] = set()
                for lst in (main, main_nogoogle, other):
                    for f in lst:
                        fam_set.add(str(f))
                for _, lst in category_sections:
                    for f in lst:
                        fam_set.add(str(f))

                def enc_family(name: str) -> str:
                    return name.replace(" ", "+")

                params = [f"family={enc_family(f)}" for f in sorted(fam_set)]
                # Chunk into multiple <link>s to avoid overly long URLs
                chunk_size = 12
                chunks = [params[i:i+chunk_size] for i in range(0, len(params), chunk_size)]
                links = []
                if chunks:
                    links.append('<link rel="preconnect" href="https://fonts.googleapis.com">')
                    links.append('<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>')
                    for ch in chunks:
                        href = "https://fonts.googleapis.com/css2?" + "&".join(ch) + "&display=swap"
                        links.append(f'<link href="{href}" rel="stylesheet">')
                font_links = "\n".join(links)
                replacements = fonts_data.get("replacements") or {}

                # Normalize replacements into mapping -> list[str]
                norm_repl = {}
                if isinstance(replacements, dict):
                    for k, v in replacements.items():
                        if isinstance(v, dict):
                            items = []
                            primary = v.get("primary")
                            alts = v.get("alternates") or []
                            if isinstance(primary, str):
                                items.append(primary)
                            if isinstance(alts, list):
                                items.extend([x for x in alts if isinstance(x, str)])
                            norm_repl[k] = items
                        elif isinstance(v, list):
                            norm_repl[k] = [x for x in v if isinstance(x, str)]

                # Render Jinja2 template
                tpl_dir = Path(__file__).parent / "templates"
                env = Environment(
                    loader=FileSystemLoader(str(tpl_dir)),
                    autoescape=select_autoescape(["html", "xml"]),
                    trim_blocks=True,
                    lstrip_blocks=True,
                )
                template = env.get_template("fonts.html.j2")

                sample_text = "Sphinx of black quartz, judge my vow — 123 ABC"
                html = template.render(
                    font_links=font_links,
                    main=main,
                    main_nogoogle=main_nogoogle,
                    other=other,
                    replacements=norm_repl,
                    category_sections=category_sections,
                    sample_text=sample_text,
                )

                fonts_html_dest = index_html_dest.parent / "fonts.html"
                with fonts_html_dest.open("w", encoding="utf-8") as f:
                    f.write(html)
                print(f"Created fonts preview: {fonts_html_dest}")
            else:
                print("docs/fonts.yaml not found; skipping fonts.html generation")
        except Exception as e:
            print(f"Warning: Unable to generate fonts.html: {e}", file=sys.stderr)
    else:
        # Single file import (original behavior)
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
    
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
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
    import_parser.add_argument(
        "--repo-url",
        dest="repo_url",
        metavar="URL",
        help="GitHub repository URL for 'Add Source File' buttons (e.g., https://github.com/owner/repo)",
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
