from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytesseract
import yaml
from PIL import Image, ImageDraw, ImageFont
import pypdfium2 as pdfium
try:
    import fitz  # PyMuPDF
except Exception:
    fitz = None


@dataclass(frozen=True)
class Region:
    id: int
    x: int
    y: int
    width: int
    height: int
    background_color: str
    contour: np.ndarray
    text: str = ""


def analyze_template(
    source_image: Path,
    output_dir: Path,
    *,
    placeholder_color: str = "#6fe600",
    tolerance: int = 20,
    edge_dilation: int = 5,
    background_sample_offset: int = 5,
    label_font_path: str | None = None,
    replace: bool = False,
) -> dict[str, Any]:
    # Determine input type and load/render to image
    img_bgr: np.ndarray
    src_suffix = source_image.suffix.lower()
    if src_suffix == ".pdf":
        # Render first page to PNG at 600 DPI using pypdfium2
        pdf = pdfium.PdfDocument(str(source_image))
        if len(pdf) == 0:
            raise ValueError(f"PDF has no pages: {source_image}")
        page = pdf[0]
        scale = 600 / 72.0  # 600 DPI
        bitmap = page.render(scale=scale, fill_color=(255, 255, 255, 255))
        pil = bitmap.to_pil()
        pdf.close()
        img_bgr = cv2.cvtColor(np.array(pil.convert("RGB")), cv2.COLOR_RGB2BGR)
        source_is_pdf = True
    else:
        img_bgr = cv2.imread(str(source_image), cv2.IMREAD_COLOR)
        if img_bgr is None:
            raise ValueError(f"Failed to load image: {source_image}")
        source_is_pdf = False

    # Create directory with base name of source file
    base = source_image.stem
    project_dir = output_dir / base
    project_dir.mkdir(parents=True, exist_ok=True)
    
    # New file names in the directory
    src_name = "src.png"
    template_name = "template.png"
    reference_name = "reference.png"
    regions_name = "regions.yaml"

    placeholder_bgr = hex_to_bgr(placeholder_color)
    mask = _color_mask(img_bgr, placeholder_bgr, tolerance=tolerance)
    contours = _find_contours(mask)
    if not contours:
        raise ValueError(
            f"No regions found for placeholder color {placeholder_color} (tolerance={tolerance})"
        )

    regions = _build_regions(
        img_bgr,
        contours,
        background_sample_offset=background_sample_offset,
    )

    # Extract text from regions using OCR
    regions = _extract_text_from_regions(img_bgr, regions)

    template_img = _make_template_image(
        img_bgr,
        regions,
        edge_dilation=edge_dilation,
    )

    reference_img = _make_reference_image(
        template_img,
        regions,
        placeholder_color=placeholder_color,
        label_font_path=label_font_path,
    )

    role_map = _guess_region_names(regions)

    # Save files in the project directory
    src_path = project_dir / src_name
    template_path = project_dir / template_name
    reference_path = project_dir / reference_name
    regions_path = project_dir / regions_name

    # Copy source image as PNG (converting if needed)
    cv2.imwrite(str(src_path), img_bgr)
    # Save processed template with regions removed
    cv2.imwrite(str(template_path), template_img)
    cv2.imwrite(str(reference_path), reference_img)

    # Check if regions file exists and preserve names if not replacing
    if not replace and regions_path.exists():
        try:
            # Load existing regions file
            with regions_path.open("r", encoding="utf-8") as f:
                existing_data = yaml.safe_load(f)
            
            if existing_data and isinstance(existing_data, dict):
                existing_regions = existing_data.get("regions", [])
                
                # Validate that regions match (same count and positions)
                if len(existing_regions) == len(regions):
                    # Create a map of (x, y, width, height) -> (name, role) from existing regions
                    existing_map = {}
                    for er in existing_regions:
                        key = (er.get("x"), er.get("y"), er.get("width"), er.get("height"))
                        existing_map[key] = (er.get("name", ""), er.get("role", ""))
                    
                    # Check if all new regions match existing positions
                    all_match = True
                    text_map = {r.id: r.text for r in regions}
                    for r in regions:
                        key = (r.x, r.y, r.width, r.height)
                        if key not in existing_map:
                            all_match = False
                            break
                    
                    if all_match:
                        # Preserve roles from existing file; use OCR text for names
                        for r in regions:
                            key = (r.x, r.y, r.width, r.height)
                            if key in existing_map:
                                _, existing_role = existing_map[key]
                                if existing_role:
                                    role_map[r.id] = existing_role
                        
                        print(f"Preserved region roles from existing {regions_name}")
                    else:
                        print(f"Warning: Region positions changed, using auto-detected roles")
                else:
                    print(f"Warning: Region count changed ({len(existing_regions)} -> {len(regions)}), using auto-detected roles")
        except Exception as e:
            print(f"Warning: Could not load existing regions file: {e}")

    # Get template dimensions
    template_height, template_width = img_bgr.shape[:2]

    # Optionally extract font info per region for PDF inputs
    pdf_fonts: dict[int, tuple[str, float]] = {}
    if source_is_pdf and fitz is not None:
        try:
            pdf_fonts = _extract_pdf_region_fonts(source_image, regions, scale=600 / 72.0)
            if not pdf_fonts:
                print("Info: PDF font extraction returned no fonts; checking alternate parser...")
        except Exception as e:
            print(f"Warning: Could not extract PDF fonts: {e}")
        # Final fallback: use embedded font names (if any) and estimate size from region height
        if not pdf_fonts:
            embedded = _extract_embedded_fonts(source_image)
            if embedded:
                chosen = embedded[0]
            else:
                chosen = "Helvetica"
            # Estimate font size in points from region height (single-line approximation)
            # size_pt ≈ 0.5 * height_px * 72 / 600, clamped to [8, 72]
            est: dict[int, tuple[str, float]] = {}
            for r in regions:
                sz_pt = max(8.0, min(72.0, (r.height * 0.5) * (72.0 / 600.0)))
                est[r.id] = (normalize_font_name(chosen), float(round(sz_pt, 1)))
            pdf_fonts = est

    # Build regions data without template/reference fields
    data: dict[str, Any] = {
        "content_color": placeholder_color.lower(),
        "width": int(template_width),
        "height": int(template_height),
        "css": [],
        "regions": [
            {
                "id": r.id,
                "name": r.text,
                "role": role_map.get(r.id, ""),
                "x": r.x,
                "y": r.y,
                "width": r.width,
                "height": r.height,
                "background_color": r.background_color,
                **({"font": pdf_fonts.get(r.id, ("", 0.0))[0], "font_size": pdf_fonts.get(r.id, ("", 0.0))[1]} if r.id in pdf_fonts else {}),
            }
            for r in regions
        ],
    }

    with regions_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    # Create index.html for the template directory
    _create_template_index_html(project_dir, base)

    return {
        "template": src_path,
        "reference": reference_path,
        "regions": regions_path,
        "count": len(regions),
    }


def hex_to_bgr(hex_color: str) -> tuple[int, int, int]:
    s = hex_color.strip().lstrip("#")
    if len(s) != 6:
        raise ValueError(f"Invalid hex color: {hex_color}")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return (b, g, r)


def bgr_to_hex(bgr: tuple[int, int, int]) -> str:
    b, g, r = (int(bgr[0]), int(bgr[1]), int(bgr[2]))
    return f"#{r:02x}{g:02x}{b:02x}"


def _color_mask(img_bgr: np.ndarray, placeholder_bgr: tuple[int, int, int], *, tolerance: int) -> np.ndarray:
    b, g, r = placeholder_bgr
    lower = np.array([max(0, b - tolerance), max(0, g - tolerance), max(0, r - tolerance)], dtype=np.uint8)
    upper = np.array([min(255, b + tolerance), min(255, g + tolerance), min(255, r + tolerance)], dtype=np.uint8)
    return cv2.inRange(img_bgr, lower, upper)


def _find_contours(mask: np.ndarray) -> list[np.ndarray]:
    contours, _hier = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    return list(contours)


def _build_regions(
    img_bgr: np.ndarray,
    contours: list[np.ndarray],
    *,
    background_sample_offset: int,
) -> list[Region]:
    raw: list[tuple[int, int, int, int, np.ndarray]] = []
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        raw.append((x, y, w, h, c))

    raw.sort(key=lambda t: (t[1], t[0]))
    regions: list[Region] = []
    for i, (x, y, w, h, contour) in enumerate(raw, start=1):
        bg_hex = _detect_background_color(
            img_bgr,
            x=x,
            y=y,
            w=w,
            h=h,
            offset=background_sample_offset,
        )
        regions.append(
            Region(
                id=i,
                x=int(x),
                y=int(y),
                width=int(w),
                height=int(h),
                background_color=bg_hex,
                contour=contour,
            )
        )
    return regions


def _extract_text_from_regions(img_bgr: np.ndarray, regions: list[Region]) -> list[Region]:
    """Extract text from placeholder regions using OCR."""
    updated_regions = []
    
    for region in regions:
        # Extract the region from the image
        roi = img_bgr[region.y:region.y + region.height, region.x:region.x + region.width]
        
        # Convert BGR to RGB for PIL
        roi_rgb = cv2.cvtColor(roi, cv2.COLOR_BGR2RGB)
        pil_image = Image.fromarray(roi_rgb)
        
        # Use pytesseract to extract text
        try:
            text = pytesseract.image_to_string(pil_image, config='--psm 6').strip()
            # Clean up the text - remove extra whitespace and newlines
            text = ' '.join(text.split())
        except Exception as e:
            print(f"Warning: OCR failed for region {region.id}: {e}")
            text = ""
        
        # Create new Region with extracted text
        updated_regions.append(
            Region(
                id=region.id,
                x=region.x,
                y=region.y,
                width=region.width,
                height=region.height,
                background_color=region.background_color,
                contour=region.contour,
                text=text,
            )
        )
    
    return updated_regions


def _guess_region_names(regions: list[Region]) -> dict[int, str]:
    names: dict[int, str] = {r.id: "" for r in regions}

    def area(r: Region) -> int:
        return r.width * r.height

    def aspect(r: Region) -> float:
        return r.width / max(1.0, float(r.height))

    # qr_code: last square-ish region (aspect near 1), but never the first region;
    # if the first square-ish is first in order, treat it as regular content.
    squareish = [r for r in regions if 0.85 <= aspect(r) <= 1.15]
    qr_region: Region | None = None
    if squareish:
        candidate = squareish[-1]
        if candidate.id != regions[0].id:
            qr_region = candidate
            names[qr_region.id] = "qr_code"

    # url: last wide+short region (or just before qr if qr is last)
    remaining = [r for r in regions if names[r.id] == ""]
    wide_short = [r for r in remaining if aspect(r) >= 2.0]
    url_region: Region | None = None
    if wide_short:
        # Prefer the last in order; if qr exists and is last, prefer the one before it
        if qr_region is not None and qr_region in wide_short:
            idx = wide_short.index(qr_region)
            if idx > 0:
                url_region = wide_short[idx - 1]
        if url_region is None:
            url_region = wide_short[-1]
        names[url_region.id] = "url"

    # time/date/place: three wide+short regions of similar size
    remaining = [r for r in regions if names[r.id] == ""]
    wsp = [r for r in remaining if aspect(r) >= 1.6]
    bucket: list[Region] = []
    if len(wsp) >= 3:
        # Bucket by rounded width/height to find similar sizes
        buckets: dict[tuple[int, int], list[Region]] = {}
        for r in wsp:
            key = (round(r.width / 10), round(r.height / 10))
            buckets.setdefault(key, []).append(r)
        bucket = max(buckets.values(), key=lambda v: len(v), default=[])
        if len(bucket) < 3:
            bucket = []
    if len(bucket) >= 3:
        bucket_sorted = [r for r in regions if r in bucket]
        for name, reg in zip(["time", "date", "place"], bucket_sorted[:3]):
            names[reg.id] = name

    # content and content2: largest remaining areas (excluding time/date/place)
    remaining = [r for r in regions if names[r.id] == ""]
    remaining_sorted = sorted(remaining, key=area, reverse=True)
    if remaining_sorted:
        names[remaining_sorted[0].id] = "content"
    if len(remaining_sorted) >= 2:
        names[remaining_sorted[1].id] = "content2"

    return names


def _detect_background_color(
    img_bgr: np.ndarray,
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    offset: int,
    strip_width: int = 2,
) -> str:
    height, width, _ = img_bgr.shape

    y0 = int(round(y + h * 0.2))
    y1 = int(round(y + h * 0.8))
    y0 = max(0, min(height - 1, y0))
    y1 = max(0, min(height, y1))
    if y1 <= y0:
        y0, y1 = max(0, y), min(height, y + h)

    samples: list[np.ndarray] = []

    left_x = x - offset
    if left_x >= 0:
        x0 = max(0, left_x - strip_width)
        x1 = min(width, left_x + 1)
        samples.append(img_bgr[y0:y1, x0:x1, :])

    right_x = x + w + offset
    if right_x < width:
        x0 = max(0, right_x)
        x1 = min(width, right_x + strip_width + 1)
        samples.append(img_bgr[y0:y1, x0:x1, :])

    if not samples:
        top_y = y - offset
        if top_y >= 0:
            y0t = max(0, top_y - strip_width)
            y1t = min(height, top_y + 1)
            samples.append(img_bgr[y0t:y1t, x : x + w, :])
        bottom_y = y + h + offset
        if bottom_y < height:
            y0b = max(0, bottom_y)
            y1b = min(height, bottom_y + strip_width + 1)
            samples.append(img_bgr[y0b:y1b, x : x + w, :])

    if not samples:
        return "#000000"

    pixels = np.concatenate([s.reshape(-1, 3) for s in samples if s.size > 0], axis=0)
    if pixels.size == 0:
        return "#000000"

    q = _quantize_rgb(pixels, step=8)
    colors, counts = np.unique(q, axis=0, return_counts=True)
    mode = colors[int(np.argmax(counts))]
    return bgr_to_hex((int(mode[0]), int(mode[1]), int(mode[2])))


def _quantize_rgb(pixels_bgr: np.ndarray, *, step: int) -> np.ndarray:
    step = max(1, int(step))
    half = step // 2
    q = ((pixels_bgr.astype(np.int16) + half) // step) * step
    return np.clip(q, 0, 255).astype(np.uint8)


def _make_template_image(
    img_bgr: np.ndarray,
    regions: list[Region],
    *,
    edge_dilation: int,
) -> np.ndarray:
    out = img_bgr.copy()
    k = max(1, int(edge_dilation))
    kernel = np.ones((k, k), np.uint8)

    for r in regions:
        region_mask = np.zeros(out.shape[:2], dtype=np.uint8)
        cv2.drawContours(region_mask, [r.contour], contourIdx=-1, color=255, thickness=-1)
        dilated = cv2.dilate(region_mask, kernel, iterations=1)
        bgr = hex_to_bgr(r.background_color)
        out[dilated > 0] = bgr

    return out


def _make_reference_image(
    template_bgr: np.ndarray,
    regions: list[Region],
    *,
    placeholder_color: str,
    label_font_path: str | None = None,
) -> np.ndarray:
    out = template_bgr.copy()
    placeholder_bgr = hex_to_bgr(placeholder_color)

    for r in regions:
        cv2.rectangle(
            out,
            (r.x, r.y),
            (r.x + r.width - 1, r.y + r.height - 1),
            placeholder_bgr,
            2,
        )

    rgb = cv2.cvtColor(out, cv2.COLOR_BGR2RGB)
    img = Image.fromarray(rgb)
    draw = ImageDraw.Draw(img)

    # Use provided font or find a suitable system font
    font_path = label_font_path or _find_font_path()
    for r in regions:
        # Create label with both ID and name
        if r.text:
            label = f"{r.id}: {r.text}"
        else:
            label = str(r.id)
        
        def _font_with_size(sz: int) -> ImageFont.ImageFont:
            if font_path:
                try:
                    return ImageFont.truetype(font_path, size=sz)
                except Exception:
                    pass
            return ImageFont.load_default()

        # Binary search to find the largest font that fits both width and height constraints
        # with proper margins for readability
        margin_factor = 0.85  # Use 85% of available space
        target_w = int(r.width * margin_factor)
        target_h = int(r.height * margin_factor)
        
        # Start with a reasonable range based on region size
        min_dimension = min(r.width, r.height)
        lo = max(12, min_dimension // 20)  # Minimum font size
        hi = max(lo + 10, min_dimension * 2)  # Maximum font size to try
        
        best = _font_with_size(lo)
        best_bbox = draw.textbbox((0, 0), label, font=best)
        
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = _font_with_size(mid)
            bb = draw.textbbox((0, 0), label, font=candidate)
            tw = bb[2] - bb[0]
            th = bb[3] - bb[1]
            
            # Check if text fits within BOTH width and height constraints
            if tw <= target_w and th <= target_h:
                best = candidate
                best_bbox = bb
                lo = mid + 1  # Try larger
            else:
                hi = mid - 1  # Too big, try smaller
        
        f = best
        bbox = best_bbox
    
        bbox = draw.textbbox((0, 0), label, font=f)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = r.x + (r.width - tw) / 2
        ty = r.y + (r.height - th) / 2

        # Thicker white outline for readability at larger sizes
        outline = max(4, min(18, (tw + th) // 90))
        for dx in range(-outline, outline + 1):
            for dy in range(-outline, outline + 1):
                if dx == 0 and dy == 0:
                    continue
                draw.text((tx + dx, ty + dy), label, font=f, fill=(255, 255, 255))
        # Solid black fill on top
        draw.text((tx, ty), label, font=f, fill=(0, 0, 0))

    out_rgb = np.array(img)
    return cv2.cvtColor(out_rgb, cv2.COLOR_RGB2BGR)


def _find_font_path() -> str | None:
    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/Library/Fonts/Arial Bold.ttf",
        "/Library/Fonts/Arial.ttf",
    )
    for name in candidates:
        p = Path(name)
        if p.exists():
            return str(p)
    return None


def normalize_font_name(name: str) -> str:
    """Normalize PDF font names for readability.
    - Removes subset prefixes like "ABCDE+FontName".
    - Trims whitespace.
    Leaves style suffixes (e.g., -Bold) intact.
    """
    s = (name or "").strip()
    if "+" in s:
        # Drop subset prefix before '+'
        s = s.split("+", 1)[1]
    return s


def _extract_pdf_region_fonts(pdf_path: Path, regions: list[Region], *, scale: float) -> dict[int, tuple[str, float]]:
    """Extract dominant font and average size for each region from a PDF.
    Uses PyMuPDF rawdict to get per-span bounding boxes and font info.
    Returns mapping: region_id -> (font_name, font_size_points).
    """
    if fitz is None:
        return {}
    doc = fitz.open(str(pdf_path))
    try:
        page = doc[0]
        text = page.get_text("rawdict")
        if not text or not text.get("blocks"):
            # Fallback to dict format if rawdict is empty
            text = page.get_text("dict")
        # Prepare region rectangles in PDF point space (72 DPI, top-left origin)
        # Current regions are based on 600 DPI pixels (top-left origin), so convert back to points and add a margin.
        px_to_pt = 72.0 / 600.0
        margin_px = 8
        reg_rects = {
            r.id: (
                (r.x - margin_px) * px_to_pt,
                (r.y - margin_px) * px_to_pt,
                (r.x + r.width + margin_px) * px_to_pt,
                (r.y + r.height + margin_px) * px_to_pt,
            )
            for r in regions
        }
        # Page height in points is needed if spans use bottom-left origin
        page_height_pt = float(page.rect.height)
        counts: dict[int, dict[tuple[str, float], int]] = {r.id: {} for r in regions}
        all_spans: list[tuple[float, float, float, float, str, float, int]] = []
        for block in text.get("blocks", []) or []:
            for line in block.get("lines", []) or []:
                for span in line.get("spans", []) or []:
                    font = span.get("font") or ""
                    size = float(span.get("size") or 0.0)
                    bbox = span.get("bbox") or getattr(line, "bbox", None)
                    if not bbox:
                        continue
                    # bbox may be a list or fitz.Rect
                    if isinstance(bbox, (list, tuple)):
                        x0, y0, x1, y1 = bbox
                    else:
                        x0, y0, x1, y1 = bbox.x0, bbox.y0, bbox.x1, bbox.y1
                    # Normalize to top-left origin: flip Y using page height
                    sy0_top = page_height_pt - y1
                    sy1_top = page_height_pt - y0
                    sx0, sy0, sx1, sy1 = x0, sy0_top, x1, sy1_top
                    chars = span.get("text") or ""
                    char_count = len(chars)
                    if char_count == 0:
                        continue
                    # Save for fallback proximity vote
                    all_spans.append((sx0, sy0, sx1, sy1, font, size, char_count))
                    # Primary: intersection-based counting
                    for rid, (rx0, ry0, rx1, ry1) in reg_rects.items():
                        if sx1 <= rx0 or sx0 >= rx1 or sy1 <= ry0 or sy0 >= ry1:
                            continue
                        key = (font, size)
                        d = counts[rid]
                        d[key] = d.get(key, 0) + char_count
        result: dict[int, tuple[str, float]] = {}
        for rid, font_map in counts.items():
            if not font_map:
                # Proximity-based fallback when no direct spans intersect the region
                rx0, ry0, rx1, ry1 = reg_rects[rid]
                rcx = (rx0 + rx1) * 0.5
                rcy = (ry0 + ry1) * 0.5
                page_diag = (page.rect.width ** 2 + page.rect.height ** 2) ** 0.5
                radius = max(36.0, page_diag * 0.10)
                font_weights: dict[str, float] = {}
                size_accum: dict[str, tuple[float, float]] = {}
                for sx0, sy0, sx1, sy1, fnt, sz, cc in all_spans:
                    scx = (sx0 + sx1) * 0.5
                    scy = (sy0 + sy1) * 0.5
                    dx = scx - rcx
                    dy = scy - rcy
                    dist = (dx * dx + dy * dy) ** 0.5
                    if dist > radius:
                        continue
                    weight = cc / (1.0 + dist)
                    font_weights[fnt] = font_weights.get(fnt, 0.0) + weight
                    if sz > 0:
                        ws, ww = size_accum.get(fnt, (0.0, 0.0))
                        size_accum[fnt] = (ws + sz * weight, ww + weight)
                if font_weights:
                    top_font = max(font_weights.items(), key=lambda kv: kv[1])[0]
                    ws, ww = size_accum.get(top_font, (0.0, 0.0))
                    size = ws / ww if ww > 0 else 0.0
                    result[rid] = (normalize_font_name(top_font), size)
                    continue
                else:
                    # No nearby spans found either; leave empty and move on
                    continue
            # Pick dominant font by char count
            (font, size), total = max(font_map.items(), key=lambda kv: kv[1])
            result[rid] = (normalize_font_name(font), size)
        # If still missing, assign the page-dominant font as a final fallback
        if len(result) < len(regions) and all_spans:
            from collections import defaultdict
            page_font_counts: dict[str, int] = defaultdict(int)
            page_font_sizes: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))
            for sx0, sy0, sx1, sy1, fnt, sz, cc in all_spans:
                page_font_counts[fnt] += cc
                if sz > 0:
                    ssum, scount = page_font_sizes[fnt]
                    page_font_sizes[fnt] = (ssum + sz * cc, scount + cc)
            if page_font_counts:
                top_font = max(page_font_counts.items(), key=lambda kv: kv[1])[0]
                ssum, scount = page_font_sizes.get(top_font, (0.0, 0))
                page_avg_size = (ssum / scount) if scount > 0 else 0.0
                for r in regions:
                    if r.id not in result:
                        result[r.id] = (normalize_font_name(top_font), page_avg_size)
        return result
    finally:
        doc.close()


def _extract_embedded_fonts(pdf_path: Path) -> list[str]:
    """Extract embedded font names from a PDF by scanning FontDescriptor objects.
    Returns a list of normalized font names (subset prefixes removed)."""
    if fitz is None:
        return []
    doc = fitz.open(str(pdf_path))
    names: list[str] = []
    try:
        import re
        for xref in range(1, doc.xref_length()):
            try:
                obj = doc.xref_object(xref) or ""
            except Exception:
                continue
            if "/Type /FontDescriptor" not in obj:
                continue
            m = re.search(r"/FontName\s*/(?:[A-Z]+\+)?([^\s/\]]+)", obj)
            if m:
                names.append(normalize_font_name(m.group(1)))
    finally:
        doc.close()
    # Deduplicate preserving order
    seen = set()
    out: list[str] = []
    for n in names:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


def _create_template_index_html(template_dir: Path, template_name: str) -> None:
    """Create an index.html file in the template directory listing all files."""
    # Get path to the template HTML file
    templates_dir = Path(__file__).parent / "templates"
    template_html = templates_dir / "template_index.html"
    
    if not template_html.exists():
        print(f"Warning: Template index HTML not found at {template_html}")
        return
    
    # Read the template
    with template_html.open('r', encoding='utf-8') as f:
        html_content = f.read()
    
    # Replace template name placeholder
    html_content = html_content.replace('{{ template_name }}', template_name)
    
    # Write to template directory
    index_path = template_dir / "index.html"
    with index_path.open('w', encoding='utf-8') as f:
        f.write(html_content)
