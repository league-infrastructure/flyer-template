#!/usr/bin/env python3
import argparse
from pathlib import Path
from typing import Iterable, List, Dict, Any

try:
    import yaml  # type: ignore
except Exception as e:  # pragma: no cover
    yaml = None


def load_yaml_fonts(source_path: Path) -> List[str]:
    if yaml is None:
        raise RuntimeError("PyYAML is required to read/write YAML. Please install pyyaml.")
    data: Any
    with source_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    # Accept either {'fonts': [...]} or a plain list [...]
    if isinstance(data, dict) and "fonts" in data and isinstance(data["fonts"], list):
        fonts = [str(x) for x in data["fonts"]]
    elif isinstance(data, list):
        fonts = [str(x) for x in data]
    else:
        raise ValueError(
            f"Unrecognized YAML structure in {source_path}. Expected a list or a dict with 'fonts'."
        )
    return fonts


def read_main_list(values: Iterable[str], file: Path | None) -> List[str]:
    items: List[str] = []
    if file:
        with file.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                items.append(line)
    for v in values or []:
        if v is None:
            continue
        # Allow comma-separated inside a single --main arg
        parts = [p.strip() for p in v.split(",")]
        items.extend([p for p in parts if p])
    # Preserve order, dedupe case-sensitively while keeping first occurrence
    seen = set()
    ordered: List[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            ordered.append(it)
    return ordered


def split_fonts(
    fonts: List[str],
    main_list: List[str],
    mode: str = "exact",
    case_insensitive: bool = False,
) -> Dict[str, List[str]]:
    if case_insensitive:
        norm = lambda s: s.lower()
    else:
        norm = lambda s: s

    main_norm = [norm(m) for m in main_list]

    def is_main(font: str) -> bool:
        f = norm(font)
        if mode == "exact":
            return f in main_norm
        if mode == "prefix":
            return any(f.startswith(m) for m in main_norm)
        raise ValueError("mode must be 'exact' or 'prefix'")

    main: List[str] = []
    other: List[str] = []
    for font in fonts:
        (main if is_main(font) else other).append(font)
    return {"main": main, "other": other}


def write_grouped_yaml(output_path: Path, grouped: Dict[str, List[str]]) -> None:
    if yaml is None:
        raise RuntimeError("PyYAML is required to read/write YAML. Please install pyyaml.")
    with output_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(grouped, f, sort_keys=False, allow_unicode=True)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Group fonts into 'main' and 'other' from test/fonts.yaml",
    )
    p.add_argument(
        "--source",
        type=Path,
        default=Path("test/fonts.yaml"),
        help="Path to YAML containing a 'fonts' list or a plain list",
    )
    p.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output YAML path (default: alongside source as fonts_grouped.yaml)",
    )
    p.add_argument(
        "--main",
        action="append",
        default=[],
        help="Font names to classify as main. Can repeat or use comma-separated values.",
    )
    p.add_argument(
        "--main-file",
        type=Path,
        default=None,
        help="File with one font name per line to classify as main.",
    )
    p.add_argument(
        "--mode",
        choices=["exact", "prefix"],
        default="exact",
        help="Match mode: exact font names or family prefix",
    )
    p.add_argument(
        "--case-insensitive",
        action="store_true",
        help="Case-insensitive matching for font names",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    source: Path = args.source
    output: Path | None = args.output
    main_values: List[str] = read_main_list(args.main, args.main_file)
    if not main_values:
        raise SystemExit(
            "No main fonts provided. Use --main and/or --main-file to specify them."
        )

    fonts = load_yaml_fonts(source)
    grouped = split_fonts(
        fonts,
        main_values,
        mode=args.mode,
        case_insensitive=args.case_insensitive,
    )
    if output is None:
        output = source.with_name("fonts_grouped.yaml")
    write_grouped_yaml(output, grouped)
    print(f"Wrote grouped fonts to: {output}")


if __name__ == "__main__":
    main()
