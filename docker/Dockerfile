FROM python:3.13-slim

# Install system dependencies for WeasyPrint, OpenCV, and Tesseract OCR
RUN apt-get update && apt-get install -y \
    libcairo2 \
    libpango-1.0-0 \
    libpangocairo-1.0-0 \
    libgdk-pixbuf-2.0-0 \
    libffi-dev \
    shared-mime-info \
    libgl1 \
    libglib2.0-0 \
    tesseract-ocr \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/
COPY README.md ./

# Install uv
RUN pip install uv

# Install project dependencies
RUN uv pip install --system -e .

# Install FastAPI and web dependencies
RUN uv pip install --system fastapi uvicorn httpx python-multipart

# Expose port
EXPOSE 8000

# Labels for Caddy
LABEL caddy=webr.jtlapp.net

# Run the web application
CMD ["uvicorn", "flyte.web:app", "--host", "0.0.0.0", "--port", "8000"]
