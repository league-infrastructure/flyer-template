#!/usr/bin/env python3
"""
Extract embedded fonts from a PDF file.

Usage: python extract_fonts.py input.pdf [output_directory]

Requires: pip install pymupdf
"""

import fitz
import sys
import os
import re


def extract_fonts(pdf_path, output_dir=None):
    """Extract all embedded fonts from a PDF."""
    
    if output_dir is None:
        output_dir = os.path.splitext(os.path.basename(pdf_path))[0] + "_fonts"
    
    os.makedirs(output_dir, exist_ok=True)
    
    doc = fitz.open(pdf_path)
    extracted = []
    
    # Build mapping: FontFile stream xref -> font name
    font_names = {}
    for i in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(i)
            if "/Type /FontDescriptor" in obj:
                # Extract font name (strip subset prefix like AAAAAA+)
                match = re.search(r'/FontName\s*/([A-Z]+\+)?([^\s/\]]+)', obj)
                if match:
                    name = match.group(2)
                    
                    # Find the FontFile reference (FontFile, FontFile2, or FontFile3)
                    for key in ["FontFile2", "FontFile3", "FontFile"]:
                        ff_match = re.search(rf'/{key}\s+(\d+)\s+\d+\s+R', obj)
                        if ff_match:
                            stream_xref = int(ff_match.group(1))
                            font_names[stream_xref] = name
                            break
        except:
            pass
    
    # Extract font streams
    for stream_xref, name in font_names.items():
        try:
            if doc.xref_is_stream(stream_xref):
                stream_data = doc.xref_stream(stream_xref)
                
                # Determine extension from magic bytes
                if stream_data[:4] == b'\x00\x01\x00\x00' or stream_data[:4] == b'true':
                    ext = ".ttf"
                elif stream_data[:4] == b'OTTO':
                    ext = ".otf"
                elif stream_data[:4] == b'wOFF':
                    ext = ".woff"
                elif stream_data[:4] == b'wOF2':
                    ext = ".woff2"
                else:
                    # Could be CFF or Type1
                    ext = ".bin"
                
                filename = f"{name}{ext}"
                filepath = os.path.join(output_dir, filename)
                
                with open(filepath, "wb") as f:
                    f.write(stream_data)
                
                extracted.append({
                    "name": name,
                    "xref": stream_xref,
                    "path": filepath,
                    "size": len(stream_data),
                    "format": ext[1:].upper()
                })
                
        except Exception as e:
            print(f"Warning: Could not extract {name}: {e}", file=sys.stderr)
    
    doc.close()
    return extracted


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} input.pdf [output_directory]")
        print()
        print("Extracts embedded fonts from a PDF file.")
        print("Fonts are saved as .ttf, .otf, or .bin based on their format.")
        print()
        print("Note: Most PDFs contain SUBSETTED fonts (only glyphs used in the doc).")
        print("These may not contain the full character set.")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    output_dir = sys.argv[2] if len(sys.argv) > 2 else None
    
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}", file=sys.stderr)
        sys.exit(1)
    
    print(f"Extracting fonts from: {pdf_path}")
    print()
    
    fonts = extract_fonts(pdf_path, output_dir)
    
    if fonts:
        print(f"Extracted {len(fonts)} font(s):")
        print("-" * 50)
        for f in fonts:
            print(f"  {f['name']}.{f['format'].lower()}")
            print(f"    Size: {f['size']:,} bytes")
            print(f"    Path: {f['path']}")
            print()
    else:
        print("No embedded fonts found (or fonts are not extractable).")
    
    return fonts


if __name__ == "__main__":
    main()
