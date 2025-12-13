#!/usr/bin/env zsh

# Install web dependencies if needed
echo "Installing web dependencies..."
uv pip install fastapi uvicorn httpx python-multipart

# Run the web server
echo "Starting Flyte web renderer on http://localhost:8088"
uvicorn flyte.web:app --host 0.0.0.0 --port 8088 --reload
