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

    base = Image.open(template_path).convert("RGBA")

    for region in regions_data.get("regions", []) or []:
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

        overlay = _render_html_to_image(html, width=w, height=h, css_text=css_text)
        base.alpha_composite(overlay, dest=(x, y))

    base.save(output_path)
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


def _render_html_to_image(html: str, *, width: int, height: int, css_text: str) -> Image.Image:
    w = max(1, int(width))
    h = max(1, int(height))

    page_css = f"""
    @page {{ size: {w}px {h}px; margin: 0; }}
    html, body {{ margin: 0; padding: 0; width: {w}px; height: {h}px; overflow: hidden; }}
    #flyte-content {{ display: inline-block; transform-origin: top left; }}
    """

    if css_text:
        page_css += "\n" + css_text

    doc_html = f"""<!doctype html>
    <html>
      <head>
        <meta charset='utf-8' />
        <style>{page_css}</style>
      </head>
      <body>
        <div id="flyte-content">{html}</div>
      </body>
    </html>
    """

    out = io.BytesIO()
    HTML(string=doc_html, base_url=str(Path.cwd())).write_png(out, stylesheets=None)
    out.seek(0)
    img = Image.open(out).convert("RGBA")

    if img.size != (w, h):
        img = img.resize((w, h))
    return img
