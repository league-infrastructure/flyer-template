# flyer-template

This repo is an installable Python application for creating and rendering flyer templates.

- Importable application/library code lives in `src/flyte/`.
- The `flyte` command is installed via a console-script entrypoint.
- Web API available via FastAPI for remote rendering.
- **Live template gallery**: Browse all templates at the [GitHub Pages site](https://league-infrastructure.github.io/flyer-template/)

## Workflow Overview

Flyte uses a three-step process to create flyers:

1. **`import`** - Analyze a template image to identify content regions and generate metadata
2. **`compile`** - Merge content with the template to generate HTML
3. **`render`** - Convert HTML to PNG or PDF for distribution

For remote rendering, a **web service** accepts URLs and returns rendered PNG or PDF files using the same rendering engine.

## Template Gallery

All templates from the `source/` directory are automatically imported and published to GitHub Pages on every push to master. Visit the live gallery to:

- Browse all available templates
- Preview template and reference images
- Download template assets (regions.yaml, source images)

The gallery is automatically updated via GitHub Actions whenever templates are added or modified in the `source/` directory.

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

### Import a template image

Generates a directory with `src.png`, `template.png`, `reference.png`, and `regions.yaml`.

```zsh
# Import a single template
flyte import path/to/template.png -o output_dir/

# Import entire directory (with subdirectories)
flyte import source/ -o templates/
```

When importing a directory, an `index.json` file is automatically created listing all templates.

Optional tuning:

```zsh
flyte import path/to/template.png -o output_dir/ --color '#6fe600' --tolerance 20 --dilate 5 --offset 5
```

Use a specific font for large reference numbers (recommended for macOS):

```zsh
flyte import path/to/template.png -o output_dir/ --label-font "/Library/Fonts/Arial Bold.ttf"
```

### Compile content into HTML

Compiles content YAML with template to generate HTML.

```zsh
flyte compile content.yaml template_dir/ -o output.html
```

With custom stylesheet:

```zsh
flyte compile content.yaml template_dir/ -o output.html -s style.css
```

### Render HTML to PNG or PDF

Renders HTML to PNG or PDF format.

```zsh
# Render to PNG
flyte render page.html -o output.png

# Render to PDF (with active links)
flyte render page.html -o output.pdf

# Specify format explicitly
flyte render page.html -o output_dir/ -f pdf
```

## Web API

Run the web server for remote rendering:

```zsh
./run_web_server.sh
```

Or with uvicorn directly:

```zsh
uvicorn flyte.web:app --host 0.0.0.0 --port 8000
```

### API Endpoints

- `GET /` - Web interface with form and documentation
- `GET /png?url=<URL>` - Render URL to PNG for display
- `POST /png` - Render URL to PNG (accepts JSON or form data)
- `GET /pdf?url=<URL>` - Render URL to PDF for download
- `POST /pdf` - Render URL to PDF (accepts JSON or form data)

Example API usage:

```bash
# GET request
curl "http://localhost:8000/png?url=https://example.com" > output.png

# POST with JSON
curl -X POST "http://localhost:8000/pdf" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com"}' > output.pdf

# POST with form data
curl -X POST "http://localhost:8000/png" \
  -F "url=https://example.com" > output.png
```

## Docker Deployment

See `docker/README.md` for Docker setup and deployment instructions.

```zsh
cd docker
docker-compose up -d
```

The service will be available at `http://localhost:8000` with Caddy label `webr.jtlapp.net`.

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
