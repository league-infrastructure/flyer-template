"""FastAPI web application for Flyte rendering."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse

from flyte.render import render_html_to_file

app = FastAPI(title="Flyte Web Renderer", version="1.0.0")


async def fetch_html_from_url(url: str) -> str:
    """Fetch HTML content from a URL using httpx."""
    async with httpx.AsyncClient(follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.text


@app.get("/", response_class=HTMLResponse)
async def index():
    """Display a form for entering URLs and API documentation."""
    return """
<!DOCTYPE html>
<html>
<head>
    <title>Flyte Web Renderer</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 50px auto;
            padding: 20px;
        }
        h1 {
            color: #333;
        }
        form {
            background: #f4f4f4;
            padding: 20px;
            border-radius: 8px;
            margin: 20px 0;
        }
        input[type="url"] {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        button {
            background: #007bff;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
        }
        button:hover {
            background: #0056b3;
        }
        .api-docs {
            background: #fff;
            padding: 20px;
            border-left: 4px solid #007bff;
            margin: 20px 0;
        }
        code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
        }
        pre {
            background: #f4f4f4;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
        }
    </style>
</head>
<body>
    <h1>Flyte Web Renderer</h1>
    
    <form method="GET" action="/png">
        <h2>Render URL to Image</h2>
        <input type="url" name="url" placeholder="Enter URL to render" required>
        <div>
            <button type="submit" formaction="/png">Render to PNG</button>
            <button type="submit" formaction="/pdf">Render to PDF</button>
        </div>
    </form>

    <div class="api-docs">
        <h2>API Documentation</h2>
        
        <h3>PNG Endpoint</h3>
        <p><strong>GET /png?url=&lt;URL&gt;</strong></p>
        <pre>curl "http://localhost:8000/png?url=https://example.com" > output.png</pre>
        
        <p><strong>POST /png</strong> (JSON)</p>
        <pre>curl -X POST "http://localhost:8000/png" \\
  -H "Content-Type: application/json" \\
  -d '{"url": "https://example.com"}' > output.png</pre>
        
        <p><strong>POST /png</strong> (Form Data)</p>
        <pre>curl -X POST "http://localhost:8000/png" \\
  -F "url=https://example.com" > output.png</pre>

        <h3>PDF Endpoint</h3>
        <p><strong>GET /pdf?url=&lt;URL&gt;</strong></p>
        <pre>curl "http://localhost:8000/pdf?url=https://example.com" > output.pdf</pre>
        
        <p><strong>POST /pdf</strong> (JSON)</p>
        <pre>curl -X POST "http://localhost:8000/pdf" \\
  -H "Content-Type: application/json" \\
  -d '{"url": "https://example.com"}' > output.pdf</pre>
        
        <p><strong>POST /pdf</strong> (Form Data)</p>
        <pre>curl -X POST "http://localhost:8000/pdf" \\
  -F "url=https://example.com" > output.pdf</pre>
    </div>
</body>
</html>
    """


@app.get("/png")
async def render_png_get(url: Annotated[str, Query(description="URL to render")]):
    """Render a URL to PNG via GET request."""
    return await _render_url(url, "png")


@app.post("/png")
async def render_png_post(request: Request, url: Annotated[str | None, Form()] = None):
    """Render a URL to PNG via POST request (form or JSON)."""
    if url is None:
        # Try to parse as JSON
        try:
            body = await request.json()
            url = body.get("url")
        except:
            pass
    
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    return await _render_url(url, "png")


@app.get("/pdf")
async def render_pdf_get(url: Annotated[str, Query(description="URL to render")]):
    """Render a URL to PDF via GET request."""
    return await _render_url(url, "pdf")


@app.post("/pdf")
async def render_pdf_post(request: Request, url: Annotated[str | None, Form()] = None):
    """Render a URL to PDF via POST request (form or JSON)."""
    if url is None:
        # Try to parse as JSON
        try:
            body = await request.json()
            url = body.get("url")
        except:
            pass
    
    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")
    return await _render_url(url, "pdf")


async def _render_url(url: str, format: str):
    """Common rendering logic for both PNG and PDF."""
    if not url:
        raise HTTPException(status_code=400, detail="URL is required")
    
    try:
        # Fetch HTML content from URL
        html_content = await fetch_html_from_url(url)
        
        # Create temporary files
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            html_file = tmp_path / "page.html"
            html_file.write_text(html_content, encoding='utf-8')
            
            # Render to requested format
            output_file = tmp_path / f"output.{format}"
            render_html_to_file(html_file, output_file)
            
            # Read the file into memory before temp directory is deleted
            file_bytes = output_file.read_bytes()
            
        # Return the rendered file from memory
        media_type = "image/png" if format == "png" else "application/pdf"
        filename = f"render.{format}"
        
        from fastapi.responses import Response
        return Response(
            content=file_bytes,
            media_type=media_type,
            headers={
                "Content-Disposition": f"{'inline' if format == 'png' else 'attachment'}; filename={filename}"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Rendering failed: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
