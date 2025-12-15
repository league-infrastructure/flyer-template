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
import base64
import io as _io
try:
    import qrcode
except Exception:
    qrcode = None


def compile_template(
    content_file: Path,
    template_dir: Path,
    output_path: Path,
    *,
    style_path: Path | None = None,
) -> Path:
    """Compile content and template into HTML."""
    regions_file = template_dir / "regions.yaml"
    if not regions_file.exists():
        raise ValueError(f"regions.yaml not found in {template_dir}")
    
    regions_data = _load_yaml(regions_file)
    
    # Look for template.png in the template directory
    template_path_option = template_dir / "template.png"
    src_path_option = template_dir / "src.png"
    
    if template_path_option.exists():
        template_path = template_path_option
    elif src_path_option.exists():
        template_path = src_path_option
    else:
        raise ValueError(f"Could not find template.png or src.png in {template_dir}")

    # Load raw content file to get CSS reference
    raw_content = _load_yaml(content_file)
    content_map = _load_content(content_file)
    
    # Load CSS - priority: command line style_path, then content file CSS, then regions YAML
    css_text = ""
    if style_path:
        css_text = style_path.read_text(encoding='utf-8')
    else:
        css_paths = []
        if "css" in raw_content:
            css_paths = [Path(raw_content["css"])]
        elif regions_data.get("css"):
            css_paths = [Path(p) for p in regions_data["css"]]
        
        if css_paths:
            css_text = _load_css(css_paths, regions_file=regions_file, content_file=content_file, css_dir=None)

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
        role = (region.get("role") or "").strip()

        html = None
        # Try to find content by name first, then role, then id
        if name and name in content_map:
            html = content_map[name]
        elif role and role in content_map:
            html = content_map[role]
        elif region_id is not None and str(region_id) in content_map:
            html = content_map[str(region_id)]

        # Special handling: generate QR code image when region name or role is 'qr_code'
        if (name == "qr_code" or role == "qr_code" or str(region_id).lower() == "qr_code") and (content_map.get("url") or content_map.get("qr_code")):
            url_value = content_map.get("qr_code") or content_map.get("url")
            if qrcode:
                qr = qrcode.QRCode(border=1, box_size=10)
                qr.add_data(url_value)
                qr.make(fit=True)
                img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
                buf = _io.BytesIO()
                img_qr.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                html = f"<img alt='QR' src='data:image/png;base64,{b64}' style='width:100%;height:100%;object-fit:contain;' />"
            else:
                html = f"<div>QR: {url_value}</div>"

        if not html:
            continue

        x = int(region["x"])
        y = int(region["y"])
        w = int(region["width"])
        h = int(region["height"])

        # Compute area and assign size category
        area = w * h
        if area < 50_000:
            size_class = "xs"
        elif area < 150_000:
            size_class = "sm"
        elif area < 300_000:
            size_class = "md"
        else:
            size_class = "lg"

        # Region identifier for id attribute
        region_id_attr = (region.get("name") or str(region.get("id")) or "").strip()

        content_divs.append(f"""
        <div id="{region_id_attr}" class="region {size_class} {name}" style="position: absolute; left: {x}px; top: {y}px; width: {w}px; height: {h}px; overflow: hidden;">
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
      /* Size-based font scaling for regions */
      .region {{
        line-height: 1.2;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        justify-content: flex-start;
        padding: 8px;
        box-sizing: border-box;
        overflow: hidden;
        text-align: left;
      }}
      .region.xs {{ font-size: 32px; }}
      .region.sm {{ font-size: 52px; }}
      .region.md {{ font-size: 72px; }}
      .region.lg {{ font-size: 90px; }}
      /* Specific tuning: URL regions often need smaller base size */
      .region.url {{ font-size: 36px; word-wrap: break-word; overflow-wrap: anywhere; text-align: center; }}
      .region.qr_code {{ display: flex; align-items: center; justify-content: center; padding: 0; }}
      .region.qr_code img {{ width: 90%; height: 90%; object-fit: contain; }}
      /* Prevent text overflow and force text wrapping */
      .region h2, .region p, .region div, .region a {{ 
        overflow-wrap: break-word;
        word-wrap: break-word;
        word-break: break-word;
        hyphens: auto;
        margin: 0;
        max-width: 100%;
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

    # Write HTML to output file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(doc_html, encoding='utf-8')
    
    return output_path


def render_template(
    regions_file: Path,
    content_file: Path,
    output_path: Path,
    *,
    css_dir: Path | None = None,
) -> Path:
    regions_data = _load_yaml(regions_file)
    
    # New format: template.png in same directory, fallback to src.png or old format with "template" field
    regions_dir = regions_file.parent
    template_path_option = regions_dir / "template.png"
    src_path_option = regions_dir / "src.png"
    
    if template_path_option.exists():
        template_path = template_path_option
    elif src_path_option.exists():
        template_path = src_path_option
    elif "template" in regions_data:
        template_path = _resolve_sibling(regions_file, Path(regions_data["template"]))
    else:
        raise ValueError(f"Could not find template image for {regions_file}")

    # Load raw content file to get CSS reference
    raw_content = _load_yaml(content_file)
    content_map = _load_content(content_file)
    
    # Load CSS from regions or content file
    css_paths = [Path(p) for p in regions_data.get("css", []) or []]
    if not css_paths and "css" in raw_content:
        css_paths = [Path(raw_content["css"])]
    
    css_text = _load_css(css_paths, regions_file=regions_file, content_file=content_file, css_dir=css_dir)

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
        role = (region.get("role") or "").strip()

        html = None
        # Try to find content by name first, then role, then id
        if name and name in content_map:
            html = content_map[name]
        elif role and role in content_map:
            html = content_map[role]
        elif region_id is not None and str(region_id) in content_map:
            html = content_map[str(region_id)]

        # Special handling: generate QR code image when region name is 'qr_code'
        if (name == "qr_code" or str(region_id).lower() == "qr_code") and (content_map.get("url") or content_map.get("qr_code")):
            url_value = content_map.get("qr_code") or content_map.get("url")
            if qrcode:
                qr = qrcode.QRCode(border=1, box_size=10)
                qr.add_data(url_value)
                qr.make(fit=True)
                img_qr = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
                buf = _io.BytesIO()
                img_qr.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode("ascii")
                html = f"<img alt='QR' src='data:image/png;base64,{b64}' style='width:100%;height:100%;object-fit:contain;' />"
            else:
                html = f"<div>QR: {url_value}</div>"

        if not html:
            continue

        x = int(region["x"])
        y = int(region["y"])
        w = int(region["width"])
        h = int(region["height"])

        # Compute area and assign size category
        area = w * h
        if area < 50_000:
            size_class = "xs"
        elif area < 150_000:
            size_class = "sm"
        elif area < 300_000:
            size_class = "md"
        else:
            size_class = "lg"

        # Region identifier for id attribute
        region_id_attr = (region.get("name") or str(region.get("id")) or "").strip()

        content_divs.append(f"""
        <div id="{region_id_attr}" class="region {size_class} {name}" style="position: absolute; left: {x}px; top: {y}px; width: {w}px; height: {h}px; overflow: hidden;">
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
      /* Size-based font scaling for regions */
      .region {{
        line-height: 1.2;
        display: flex;
        flex-direction: column;
        align-items: flex-start;
        justify-content: flex-start;
        padding: 8px;
        box-sizing: border-box;
        overflow: hidden;
        text-align: left;
      }}
      .region.xs {{ font-size: 32px; }}
      .region.sm {{ font-size: 52px; }}
      .region.md {{ font-size: 72px; }}
      .region.lg {{ font-size: 90px; }}
      /* Specific tuning: URL regions often need smaller base size */
      .region.url {{ font-size: 36px; word-wrap: break-word; overflow-wrap: anywhere; text-align: center; }}
      .region.qr_code {{ display: flex; align-items: center; justify-content: center; padding: 0; }}
      .region.qr_code img {{ width: 90%; height: 90%; object-fit: contain; }}
      /* Prevent text overflow and force text wrapping */
      .region h2, .region p, .region div, .region a {{ 
        overflow-wrap: break-word;
        word-wrap: break-word;
        word-break: break-word;
        hyphens: auto;
        margin: 0;
        max-width: 100%;
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


def _load_css(css_paths: list[Path], *, regions_file: Path, content_file: Path | None = None, css_dir: Path | None) -> str:
    parts: list[str] = []
    for p in css_paths:
        candidate = p
        if not candidate.is_absolute():
            if css_dir is not None:
                candidate = css_dir / candidate
            else:
                # Try resolving in order: cwd, content file parent, regions file parent
                candidates = [Path.cwd() / candidate]
                if content_file is not None:
                    candidates.append(content_file.parent / candidate)
                candidates.append(regions_file.parent / candidate)
                
                candidate = None
                for c in candidates:
                    if c.exists():
                        candidate = c
                        break
                
                if candidate is None:
                    candidate = candidates[0]  # Default to first if none found
        
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


def render_html_to_file(
    html_file: Path,
    output_path: Path,
) -> Path:
    """Render an HTML file to PNG or PDF based on output extension."""
    html_content = html_file.read_text(encoding='utf-8')
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Determine output format from extension
    output_ext = output_path.suffix.lower()
    
    if output_ext == '.pdf':
        # Render to PDF with active links
        HTML(string=html_content, base_url=str(html_file.parent)).write_pdf(output_path)
    elif output_ext == '.png':
        # Render to PNG
        # First render to PDF
        pdf_bytes = io.BytesIO()
        HTML(string=html_content, base_url=str(html_file.parent)).write_pdf(pdf_bytes)
        pdf_bytes.seek(0)
        
        # Convert PDF to PNG using pypdfium2
        pdf = pdfium.PdfDocument(pdf_bytes)
        page = pdf[0]
        
        # Render with transparent background
        bitmap = page.render(scale=1.0, fill_color=(0, 0, 0, 0))
        pil_image = bitmap.to_pil()
        
        pdf.close()
        
        # Save as PNG
        img = pil_image.convert("RGBA")
        img.save(output_path)
    else:
        raise ValueError(f"Unsupported output format: {output_ext}. Use .png or .pdf")
    
    return output_path
