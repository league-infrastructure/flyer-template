# flyer-template

This repo is an installable Python application (not just a single script).

- Importable application/library code lives in `src/flyte/`.
- The `flyte` command is installed via a console-script entrypoint.

## Try it locally (pip)

```zsh
python -m pip install -e .
flyte
```

## Try it locally (uv)

```zsh
uv sync
uv run flyte
```

## Commands

### Import/analyze a template image

Generates `{stem}_template.png`, `{stem}_reference.png`, and `{stem}_regions.yaml`.

```zsh
flyte -i path/to/template.png -o out/
```

Optional tuning:

```zsh
flyte -i path/to/template.png -o out/ --color '#6fe600' --tolerance 20 --dilate 5 --offset 5
```

Use a specific font for large reference numbers (recommended for macOS):

```zsh
flyte -i path/to/template.png -o out/ --label-font "/Library/Fonts/Arial Bold.ttf"
```

### Render content into a template

Renders HTML snippets from a YAML/JSON content map into the regions and composites onto the template.

```zsh
flyte -r out/template_regions.yaml -c path/to/content.yaml -o out/rendered.png
```

HTML rendering is browser-free and uses WeasyPrint.

## System dependencies for WeasyPrint (macOS)

```zsh
brew install weasyprint
```

On Linux production hosts, install the equivalent Cairo/Pango/GDK-Pixbuf/FreeType/HarfBuzz/Fribidi packages.

## Install with pipx

From this repo root:

```zsh
pipx install .
flyte
```

## Layout

- `src/flyte/hello.py` contains `hello_world()`
- `src/flyte/cli.py` contains `main()` (entrypoint)
- `main.py` is just a thin wrapper that calls `flyte.cli:main`
