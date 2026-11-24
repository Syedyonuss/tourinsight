"""Wait for the local API to respond, then open the TourInsight site."""
from __future__ import annotations
import sys
import time
import urllib.error
import urllib.request
import webbrowser

base_url = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://127.0.0.1:8501"
health_url = base_url + "/api/health"
for _ in range(90):
    try:
        with urllib.request.urlopen(health_url, timeout=2) as response:
            if response.status == 200:
                webbrowser.open(base_url)
                raise SystemExit(0)
    except (urllib.error.URLError, TimeoutError, OSError):
        time.sleep(1)
print(f"TourInsight did not become ready. Open this address after checking the server terminal: {base_url}", file=sys.stderr)
raise SystemExit(1)
