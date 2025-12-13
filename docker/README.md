# Flyte Web Renderer - Docker Setup

This directory contains Docker configuration for running the Flyte web renderer service.

## Quick Start

Build and run the service:

```bash
cd docker
docker-compose up -d
```

The service will be available at `http://localhost:8000`

## Configuration

The service is configured with the Caddy label `webr.jtlapp.net` for reverse proxy integration.

### Environment Variables

- `PYTHONUNBUFFERED=1` - Ensures Python output is sent straight to terminal

### Ports

- `8000` - HTTP API endpoint

## Building

Build the Docker image:

```bash
docker-compose build
```

## Running

Start the service:

```bash
docker-compose up -d
```

View logs:

```bash
docker-compose logs -f
```

Stop the service:

```bash
docker-compose down
```

## API Endpoints

- `GET /` - Web interface with form and documentation
- `GET /png?url=<URL>` - Render URL to PNG
- `POST /png` - Render URL to PNG (JSON or form data)
- `GET /pdf?url=<URL>` - Render URL to PDF
- `POST /pdf` - Render URL to PDF (JSON or form data)

## Development

For development, the source code is mounted as a read-only volume. To make changes effective, rebuild the container:

```bash
docker-compose up -d --build
```
