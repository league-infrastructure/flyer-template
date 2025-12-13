#!/usr/bin/env python
"""Test script for the web API."""

import sys
import time
import subprocess
import requests
from pathlib import Path

def main():
    # Start the server
    print("Starting web server...")
    server = subprocess.Popen(
        ["uv", "run", "uvicorn", "flyte.web:app", "--host", "127.0.0.1", "--port", "8088"],
        cwd=Path(__file__).parent.parent,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    
    # Wait for server to start
    time.sleep(3)
    
    try:
        # Test homepage
        print("\n✓ Testing GET /")
        response = requests.get("http://localhost:8088/")
        assert response.status_code == 200
        assert "Flyte Web Renderer" in response.text
        print("  Homepage works!")
        
        # Test PNG endpoint with example.com
        print("\n✓ Testing GET /png?url=https://example.com")
        response = requests.get("http://localhost:8088/png?url=https://example.com")
        assert response.status_code == 200
        assert response.headers['content-type'] == 'image/png'
        assert len(response.content) > 1000  # Should be a real PNG
        print(f"  PNG rendered! Size: {len(response.content)} bytes")
        
        # Save for inspection
        output_file = Path("/tmp/flyte_test_render.png")
        output_file.write_bytes(response.content)
        print(f"  Saved to: {output_file}")
        
        # Test PDF endpoint
        print("\n✓ Testing GET /pdf?url=https://example.com")
        response = requests.get("http://localhost:8088/pdf?url=https://example.com")
        assert response.status_code == 200
        assert response.headers['content-type'] == 'application/pdf'
        assert len(response.content) > 1000  # Should be a real PDF
        print(f"  PDF rendered! Size: {len(response.content)} bytes")
        
        # Test POST with JSON
        print("\n✓ Testing POST /png with JSON")
        response = requests.post(
            "http://localhost:8088/png",
            json={"url": "https://example.com"}
        )
        assert response.status_code == 200
        assert response.headers['content-type'] == 'image/png'
        print("  POST with JSON works!")
        
        print("\n✅ All tests passed!")
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        # Stop the server
        print("\nStopping server...")
        server.terminate()
        server.wait(timeout=5)

if __name__ == "__main__":
    main()
