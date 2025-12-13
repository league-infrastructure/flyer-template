from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flyte.render import render_template
from flyte.template_analyzer import analyze_template


@dataclass(frozen=True)
class Flyte:
    data_dir: Path
    css_dir: Path | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data_dir", Path(self.data_dir))
        if self.css_dir is not None:
            object.__setattr__(self, "css_dir", Path(self.css_dir))

    def import_template(
        self,
        source_image: str | Path,
        output_dir: str | Path | None = None,
        *,
        placeholder_color: str = "#6fe600",
        tolerance: int = 20,
        edge_dilation: int = 5,
        background_sample_offset: int = 5,
        label_font: str | None = None,
    ) -> dict[str, Any]:
        src = self._resolve(Path(source_image))
        out_dir = self._resolve(Path(output_dir)) if output_dir is not None else self.data_dir
        out_dir.mkdir(parents=True, exist_ok=True)

        return analyze_template(
            src,
            out_dir,
            placeholder_color=placeholder_color,
            tolerance=tolerance,
            edge_dilation=edge_dilation,
            background_sample_offset=background_sample_offset,
            label_font_path=label_font,
        )

    def render(
        self,
        regions_file: str | Path,
        content_file: str | Path,
        output: str | Path,
    ) -> Path:
        regions_path = self._resolve(Path(regions_file))
        content_path = self._resolve(Path(content_file))
        output_path = self._resolve(Path(output))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        return render_template(
            regions_path,
            content_path,
            output_path,
            css_dir=self.css_dir,
        )

    def _resolve(self, path: Path) -> Path:
        return path if path.is_absolute() else (self.data_dir / path)
