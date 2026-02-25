"""
FireBridge — Local Test Script
Simulates Pano AI detection webhooks against the running FastAPI server.

Usage:
    python test_webhook.py

Make sure FireBridge is running first:
    uvicorn main:app --reload --port 8000
"""

import requests
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def print_response(label: str, r: requests.Response):
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"  Status: {r.status_code}")
    print(f"{'='*60}")
    try:
        print(json.dumps(r.json(), indent=2))
    except Exception:
        print(r.text)

# ── Test 1: Health Check ───────────────────────────────────────────────────────
r = requests.get(f"{BASE_URL}/health")
print_response("HEALTH CHECK", r)

# ── Test 2: High-confidence detection (Ventura County, CA) ────────────────────
payload_ventura = {
    "detection_id": "PANO-2024-00142",
    "latitude": 34.2521,
    "longitude": -119.7534,
    "confidence": 0.91,
    "camera_id": "CAM-VENTURA-07",
    "detected_at": datetime.utcnow().isoformat(),
    "notes": "Smoke plume visible, NW quadrant — Thomas Fire reference area"
}
r = requests.post(f"{BASE_URL}/webhook/pano-detection", json=payload_ventura)
print_response("HIGH-CONFIDENCE DETECTION — Ventura County, CA", r)

# ── Test 3: Low-confidence detection (should be flagged, not dispatched) ───────
payload_low_conf = {
    "detection_id": "PANO-2024-00143",
    "latitude": 34.2521,
    "longitude": -119.7534,
    "confidence": 0.32,
    "camera_id": "CAM-VENTURA-08",
    "detected_at": datetime.utcnow().isoformat(),
    "notes": "Possible heat shimmer — low confidence"
}
r = requests.post(f"{BASE_URL}/webhook/pano-detection", json=payload_low_conf)
print_response("LOW-CONFIDENCE DETECTION — Should be flagged", r)

# ── Test 4: Different region (Los Angeles County) ─────────────────────────────
payload_la = {
    "detection_id": "PANO-2024-00144",
    "latitude": 34.1478,
    "longitude": -118.1445,
    "confidence": 0.87,
    "camera_id": "CAM-LA-COUNTY-12",
    "detected_at": datetime.utcnow().isoformat(),
    "notes": "Confirmed smoke — Altadena area"
}
r = requests.post(f"{BASE_URL}/webhook/pano-detection", json=payload_la)
print_response("HIGH-CONFIDENCE DETECTION — Los Angeles County, CA", r)

print(f"\n{'='*60}")
print("  All tests complete. Check firebridge.log for full detail.")
print(f"{'='*60}\n")