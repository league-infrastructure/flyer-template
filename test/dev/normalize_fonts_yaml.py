#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import List, Dict, Any

try:
    import yaml  # type: ignore
except Exception:
    yaml = None


def strip_suffix(name: str) -> str:
    # Remove substring after the first '-' to get the family name
    parts = name.split("-", 1)
    return parts[0].strip()


def dedupe_preserve_order(items: List[str]) -> List[str]:
    seen = set()
    out: List[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out


def normalize_lists(obj: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    for key in keys:
        if key in obj and isinstance(obj[key], list):
            families = [strip_suffix(str(x)) for x in obj[key]]
            obj[key] = dedupe_preserve_order(families)
    return obj


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize test/fonts.yaml by removing weight suffixes and deduplicating lists.")
    parser.add_argument("--file", type=Path, default=Path("test/fonts.yaml"), help="Path to fonts YAML file")
    args = parser.parse_args()

    if yaml is None:
        raise SystemExit("PyYAML is required. Install with: pip install pyyaml")

    with args.file.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    # Support both old structure (directory/documents/fonts) and new grouped structure
    if isinstance(data, dict) and "fonts" in data:
        # Single list: normalize it only
        data["fonts"] = dedupe_preserve_order([strip_suffix(str(x)) for x in data["fonts"]])
    elif isinstance(data, dict):
        # Grouped structure: main/main_nogoogle/other
        keys = [k for k in ("main", "main_nogoogle", "other") if k in data]
        if not keys:
            raise SystemExit("No 'fonts' or grouped lists found in YAML.")
        data = normalize_lists(data, keys)
    else:
        raise SystemExit("Unrecognized YAML format.")

    with args.file.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
    print(f"Normalized and updated: {args.file}")


if __name__ == "__main__":
    main()
