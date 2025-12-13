from __future__ import annotations

import ctypes
import io
import json
import os
import sys
from pathlib import Path
from typing import Any

import yaml
from PIL import Image

# On macOS with Homebrew, help CFFI find gobject when running inside a venv.
if sys.platform == "darwin":
    os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")
    try:
        ctypes.CDLL("/opt/homebrew/lib/libgobject-2.0.dylib")
    except OSError:
        pass

from weasyprint import CSS, HTML
import pypdfium2 as pdfium


def render_template(
    regions_file: Path,
    content_file: Path,
    output_path: Path,
    *,
    css_dir: Path | None = None,
) -> Path:
    regions_data = _load_yaml(regions_file)
    template_path = _resolve_sibling(regions_file, Path(regions_data["template"]))

    content_map = _load_content(content_file)
    css_paths = [Path(p) for p in regions_data.get("css", []) or []]
    css_text = _load_css(css_paths, regions_file=regions_file, css_dir=css_dir)

    # Get template dimensions
    template_img = Image.open(template_path)
    template_width, template_height = template_img.size

    # Build HTML with all content regions as absolutely positioned divs
    regions = regions_data.get("regions", []) or []
    
    # Build the content divs
    content_divs = []
    for region in regions:
        region_id = region.get("id")
        name = (region.get("name") or "").strip()

        html = None
        if name and name in content_map:
            html = content_map[name]
        elif region_id is not None and str(region_id) in content_map:
            html = content_map[str(region_id)]

        if not html:
            continue

        x = int(region["x"])
        y = int(region["y"])
        w = int(region["width"])
        h = int(region["height"])

        content_divs.append(f"""
    <div style="position: absolute; left: {x}px; top: {y}px; width: {w}px; height: {h}px; overflow: hidden;">
      {html}
    </div>
    """)

    content_html = "\n".join(content_divs)

    # Create the full HTML with template as background image
    doc_html = f"""<!doctype html>
<html>
  <head>
    <meta charset='utf-8' />
    <style>
      @page {{ size: {template_width}px {template_height}px; margin: 0; }}
      html, body {{
        margin: 0;
        padding: 0;
        width: {template_width}px;
        height: {template_height}px;
        overflow: hidden;
        background-image: url('file://{template_path}');
        background-size: {template_width}px {template_height}px;
        background-repeat: no-repeat;
        position: relative;
      }}
      #container {{
        position: relative;
        width: {template_width}px;
        height: {template_height}px;
      }}
      {css_text}
    </style>
  </head>
  <body>
    <div id="container">
      {content_html}
    </div>
  </body>
</html>
    """

    # Write HTML to output directory for debugging
    html_output_path = output_path.with_suffix('.html')
    html_output_path.parent.mkdir(parents=True, exist_ok=True)
    html_output_path.write_text(doc_html, encoding='utf-8')

    # Render HTML to image
    rendered = _render_html_to_image_single(doc_html, width=template_width, height=template_height)
    rendered.save(output_path)
    
    return output_path


def _load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid regions yaml: {path}")
    return data


def _load_content(path: Path) -> dict[str, str]:
    raw: Any
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        raw = json.loads(text)
    else:
        try:
            raw = yaml.safe_load(text)
        except Exception:
            raw = json.loads(text)

    if not isinstance(raw, dict):
        raise ValueError("Content file must be a JSON/YAML object mapping ids/names to HTML")

    # If the content file has a 'content' key, use that as the actual content mapping
    # This supports content files that include metadata (template, regions, css) alongside content
    if "content" in raw and isinstance(raw["content"], dict):
        raw = raw["content"]

    out: dict[str, str] = {}
    for k, v in raw.items():
        if v is None:
            continue
        out[str(k)] = str(v)
    return out


def _resolve_sibling(regions_file: Path, relative_or_abs: Path) -> Path:
    return relative_or_abs if relative_or_abs.is_absolute() else (regions_file.parent / relative_or_abs)


def _load_css(css_paths: list[Path], *, regions_file: Path, css_dir: Path | None) -> str:
    parts: list[str] = []
    for p in css_paths:
        candidate = p
        if not candidate.is_absolute():
            if css_dir is not None:
                candidate = css_dir / candidate
            else:
                candidate = regions_file.parent / candidate
        if candidate.exists():
            parts.append(candidate.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _render_html_to_image_single(html: str, *, width: int, height: int) -> Image.Image:
    """Render a complete HTML document to an image."""
    w = max(1, int(width))
    h = max(1, int(height))

    # Render HTML to PDF using WeasyPrint
    pdf_bytes = io.BytesIO()
    HTML(string=html, base_url=str(Path.cwd())).write_pdf(pdf_bytes)
    pdf_bytes.seek(0)
    
    # Convert PDF to PNG using pypdfium2
    pdf = pdfium.PdfDocument(pdf_bytes)
    page = pdf[0]
    
    # Render with transparent background
    bitmap = page.render(scale=1.0, fill_color=(0, 0, 0, 0))
    pil_image = bitmap.to_pil()
    
    pdf.close()
    
    # Convert to RGBA and ensure correct size
    img = pil_image.convert("RGBA")
    if img.size != (w, h):
        img = img.resize((w, h), Image.Resampling.LANCZOS)
    
    return img
