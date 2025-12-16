#!/usr/bin/env python3
"""
PDF Font Reporter

Scans a directory for PDF files and reports the fonts and font sizes used.

It will try to use PyMuPDF (fitz) if installed for accurate font span data,
falling back to pdfminer.six when PyMuPDF is unavailable.

Usage:
  python test/dev/pdf_fonts.py /path/to/pdfs [--recursive] [--json] [--normalize]

Examples:
  python test/dev/pdf_fonts.py ./templates --recursive
  python test/dev/pdf_fonts.py /Users/eric/Downloads/7567661131536680103 --json

Dependencies (install if not present):
  uv pip install PyMuPDF pdfminer.six

"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Optional imports - we'll test availability at runtime
try:
    import fitz  # PyMuPDF
    HAS_MUPDF = True
except Exception:
    HAS_MUPDF = False

try:
    from pdfminer.high_level import extract_pages
    from pdfminer.layout import LTChar
    HAS_PDFMINER = True
except Exception:
    HAS_PDFMINER = False


@dataclass
class FontUse:
    font: str
    size: float
    count: int = 0


def normalize_font_name(name: str) -> str:
    """Normalize font names by stripping subset prefixes like 'ABCDEE+'.
    E.g., 'ABCDEE+Helvetica' -> 'Helvetica'.
    """
    if "+" in name:
        return name.split("+", 1)[1]
    return name


def collect_with_mupdf(pdf_path: Path, normalize: bool) -> List[FontUse]:
    font_map: Dict[Tuple[str, float], int] = {}
    doc = fitz.open(pdf_path)
    try:
        for page in doc:  # type: ignore
            data = page.get_text("dict")
            for block in data.get("blocks", []):
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        font_name = span.get("font") or "Unknown"
                        size = float(span.get("size") or 0)
                        if normalize:
                            font_name = normalize_font_name(font_name)
                        key = (font_name, size)
                        font_map[key] = font_map.get(key, 0) + len(span.get("text", ""))
    finally:
        doc.close()
    return [FontUse(font=f, size=s, count=c) for (f, s), c in sorted(font_map.items(), key=lambda x: (x[0][0].lower(), x[0][1]))]


def collect_with_pdfminer(pdf_path: Path, normalize: bool) -> List[FontUse]:
    font_map: Dict[Tuple[str, float], int] = {}
    for page_layout in extract_pages(str(pdf_path)):
        for element in page_layout:
            # Traverse recursively to find LTChar
            stack = [element]
            while stack:
                node = stack.pop()
                try:
                    if isinstance(node, LTChar):
                        font_name = getattr(node, "fontname", "Unknown")
                        size = float(getattr(node, "size", 0))
                        if normalize:
                            font_name = normalize_font_name(font_name)
                        key = (font_name, size)
                        font_map[key] = font_map.get(key, 0) + 1
                    else:
                        # Add children if node has them
                        children = getattr(node, "_objs", None)
                        if children:
                            stack.extend(children)
                except Exception:
                    # Be resilient to odd nodes
                    continue
    return [FontUse(font=f, size=s, count=c) for (f, s), c in sorted(font_map.items(), key=lambda x: (x[0][0].lower(), x[0][1]))]


def analyze_pdf(pdf_path: Path, prefer_mupdf: bool, normalize: bool) -> Tuple[str, List[FontUse]]:
    if prefer_mupdf and HAS_MUPDF:
        try:
            return (pdf_path.name, collect_with_mupdf(pdf_path, normalize))
        except Exception:
            # Fall back if PyMuPDF fails on a specific file
            pass
    if HAS_PDFMINER:
        return (pdf_path.name, collect_with_pdfminer(pdf_path, normalize))
    # Neither backend available
    return (pdf_path.name, [])


def find_pdfs(root: Path, recursive: bool) -> List[Path]:
    if recursive:
        return sorted([p for p in root.rglob("*.pdf")])
    return sorted([p for p in root.glob("*.pdf")])


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Report fonts and sizes used in PDFs")
    parser.add_argument("directory", type=str, help="Directory containing PDF files")
    parser.add_argument("--recursive", action="store_true", help="Recurse into subdirectories")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of text")
    parser.add_argument("--prefer-mupdf", action="store_true", help="Prefer PyMuPDF if available")
    parser.add_argument("--normalize", action="store_true", help="Normalize font names (strip subset prefixes)")
    args = parser.parse_args(argv)

    root = Path(args.directory).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        print(f"Error: '{root}' is not a directory", file=sys.stderr)
        return 2

    pdfs = find_pdfs(root, recursive=args.recursive)
    if not pdfs:
        print("No PDF files found.")
        return 0

    prefer_mupdf = args.prefer_mupdf or HAS_MUPDF

    results: Dict[str, List[FontUse]] = {}
    for pdf in pdfs:
        name, uses = analyze_pdf(pdf, prefer_mupdf=prefer_mupdf, normalize=args.normalize)
        results[name] = uses

    # Aggregate: font popularity across documents and common rounded sizes
    total_docs = len(pdfs)
    # Font -> set of docs using it
    font_docs: Dict[str, set] = {}
    # Rounded size (nearest 5) -> frequency across all occurrences
    size_counts: Dict[int, int] = {}

    for name, uses in results.items():
        fonts_in_doc = set()
        for u in uses:
            fonts_in_doc.add(u.font)
            rounded = int(round(u.size / 5.0) * 5)
            size_counts[rounded] = size_counts.get(rounded, 0) + u.count
        for f in fonts_in_doc:
            font_docs.setdefault(f, set()).add(name)

    # Build sorted popularity list
    popularity = [
        (font, len(docset), (len(docset) / total_docs * 100.0))
        for font, docset in font_docs.items()
    ]
    popularity.sort(key=lambda x: (-x[1], x[0].lower()))

    # Output
    if args.json:
        out = {
            "directory": str(root),
            "documents": total_docs,
            "backend": "PyMuPDF" if prefer_mupdf and HAS_MUPDF else ("pdfminer.six" if HAS_PDFMINER else "none"),
            "font_popularity": [
                {"font": f, "docs": d, "percent": round(p, 2)} for f, d, p in popularity
            ],
            "common_sizes": [
                {"size": s, "count": c} for s, c in sorted(size_counts.items())
            ],
        }
        print(json.dumps(out, indent=2))
        return 0

    # Text output
    print(f"Analyzing '{root}' — {total_docs} PDF(s)")
    print(f"Backend: {'PyMuPDF' if prefer_mupdf and HAS_MUPDF else ('pdfminer.six' if HAS_PDFMINER else 'none')}\n")
    print("Font popularity (most → least):")
    for font, docs, pct in popularity:
        print(f"  {font}: {docs}/{total_docs} ({pct:.2f}%)")
    print("\nCommon font sizes (rounded to nearest 5):")
    for size, count in sorted(size_counts.items()):
        print(f"  {size}: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
