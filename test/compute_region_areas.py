from __future__ import annotations

import yaml
from pathlib import Path

EXAMPLES_DIR = Path('test/examples')

# Define 4 categories by area thresholds (in sq pixels)
# You can tune these thresholds as needed
CATEGORIES = [
    ("xs", 0, 50_000),
    ("sm", 50_000, 150_000),
    ("md", 150_000, 300_000),
    ("lg", 300_000, float('inf')),
]


def classify(area: int) -> str:
    for name, lo, hi in CATEGORIES:
        if lo <= area < hi:
            return name
    return "lg"


def main() -> None:
    files = sorted(EXAMPLES_DIR.glob('*_regions.yaml'))
    if not files:
        print("No regions YAML files found.")
        return

    summary: list[str] = []

    for fp in files:
        with fp.open('r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        regions = data.get('regions') or []
        if not isinstance(regions, list):
            continue
        summary.append(f"\nFile: {fp}")
        for r in regions:
            name = (r.get('name') or str(r.get('id')) or '').strip()
            w = int(r.get('width', 0))
            h = int(r.get('height', 0))
            area = w * h
            cat = classify(area)
            summary.append(f" - {name:20s} area={area:7d} px^2  category={cat}")

    print("\n".join(summary))


if __name__ == '__main__':
    main()
