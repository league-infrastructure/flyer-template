from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from flyte.render import compile_template, render_html_to_file, render_template
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
        replace: bool = False,
    ) -> dict[str, Any]:
        src = self._resolve(Path(source_image))
        
        # Default output directory is the same directory as the source file
        if output_dir is not None:
            out_dir = self._resolve(Path(output_dir))
        else:
            out_dir = src.parent
        
        out_dir.mkdir(parents=True, exist_ok=True)

        return analyze_template(
            src,
            out_dir,
            placeholder_color=placeholder_color,
            tolerance=tolerance,
            edge_dilation=edge_dilation,
            background_sample_offset=background_sample_offset,
            label_font_path=label_font,
            replace=replace,
        )

    def compile(
        self,
        content_file: str | Path,
        template_dir: str | Path,
        output: str | Path,
        *,
        style: str | Path | None = None,
    ) -> Path:
        content_path = self._resolve(Path(content_file))
        template_path = self._resolve(Path(template_dir))
        output_path = self._resolve(Path(output))
        style_path = self._resolve(Path(style)) if style else None
        
        return compile_template(
            content_path,
            template_path,
            output_path,
            style_path=style_path,
        )

    def render_html(
        self,
        html_file: str | Path,
        output: str | Path,
    ) -> Path:
        html_path = self._resolve(Path(html_file))
        output_path = self._resolve(Path(output))
        
        return render_html_to_file(html_path, output_path)

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
