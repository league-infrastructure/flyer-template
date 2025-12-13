from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml
from PIL import Image, ImageDraw, ImageFont


@dataclass(frozen=True)
class Region:
    id: int
    x: int
    y: int
    width: int
    height: int
    background_color: str
    contour: np.ndarray


def analyze_template(
    source_image: Path,
    output_dir: Path,
    *,
    placeholder_color: str = "#6fe600",
    tolerance: int = 20,
    edge_dilation: int = 5,
    background_sample_offset: int = 5,
    label_font_path: str | None = None,
) -> dict[str, Any]:
    img_bgr = cv2.imread(str(source_image), cv2.IMREAD_COLOR)
    if img_bgr is None:
        raise ValueError(f"Failed to load image: {source_image}")

    base = source_image.stem
    template_name = f"{base}_template.png"
    reference_name = f"{base}_reference.png"
    regions_name = f"{base}_regions.yaml"

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

    name_map = _guess_region_names(regions)

    output_dir.mkdir(parents=True, exist_ok=True)
    template_path = output_dir / template_name
    reference_path = output_dir / reference_name
    regions_path = output_dir / regions_name

    cv2.imwrite(str(template_path), template_img)
    cv2.imwrite(str(reference_path), reference_img)

    data: dict[str, Any] = {
        "source": source_image.name,
        "template": template_name,
        "reference": reference_name,
        "content_color": placeholder_color.lower(),
        "css": [],
        "regions": [
            {
                "id": r.id,
                "name": name_map.get(r.id, ""),
                "x": r.x,
                "y": r.y,
                "width": r.width,
                "height": r.height,
                "background_color": r.background_color,
            }
            for r in regions
        ],
    }

    with regions_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False)

    return {
        "template": template_path,
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

    font_path = "/System/Library/Fonts/Helvetica.ttc"
    for r in regions:
        label = str(r.id)
        # Aggressively size the label using a real TrueType font when available.
        base_size = int(max(64, round(min(r.width, r.height) * 0.7)))
        def _font_with_size(sz: int) -> ImageFont.ImageFont:

            if font_path:
                try:
                    return ImageFont.truetype(font_path, size=sz)
                except Exception:
                    pass
            return ImageFont.load_default()

        # Binary search to fit within the box.
        lo, hi = 32, max(200, base_size)
        best = _font_with_size(lo)
        best_bbox = draw.textbbox((0, 0), label, font=best)
        target_w = int(r.width * 0.6)
        target_h = int(r.height * 0.6)
        while lo <= hi:
            mid = (lo + hi) // 2
            candidate = _font_with_size(mid)
            bb = draw.textbbox((0, 0), label, font=candidate)
            tw = bb[2] - bb[0]
            th = bb[3] - bb[1]
            if tw <= target_w and th <= target_h:
                best = candidate
                best_bbox = bb
                lo = mid + 1
            else:
                hi = mid - 1
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
