<div align="center">

# 🔥 FireBridge

### From smoke to sirens.

**Middleware that connects Pano AI wildfire detection to mass notification platforms — automatically.**

![FireBridge](https://img.shields.io/badge/version-0.1.0-FF4500?style=flat-square)
![Python](https://img.shields.io/badge/python-3.12-white?style=flat-square)
![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat-square)
![License](https://img.shields.io/badge/license-MIT-orange?style=flat-square)

</div>

---

## What is FireBridge?

FireBridge is a middleware system that closes the gap between wildfire detection and community notification. The moment a Pano AI camera detects smoke, FireBridge:

1. **Receives** the detection webhook (GPS coordinates + confidence score)
2. **Pulls** live wind data from the NOAA NWS API (speed and direction)
3. **Calculates** a wind-skewed evacuation zone polygon in GeoJSON
4. **Routes** the event to the correct county and notification platform
5. **Formats** a full payload for CodeRED or Everbridge
6. **Renders** an interactive map with the full dispatch log

No human in the loop. Detection to dispatch in under 3 seconds.

---

## Wind Intelligence

A wildfire driven by 40 mph Diablo winds behaves completely differently than one in calm conditions. FireBridge uses real NOAA wind data to skew the evacuation zone polygon downwind — ensuring the right people get notified.

| Scenario | Speed | Direction | Zone Skew |
|----------|-------|-----------|-----------|
| Santa Ana | 35 mph | NE | 2.75x |
| Diablo | 40 mph | NE | 3.0x |
| Marine Flow | 15 mph | W | 1.75x |
| Calm | 0 mph | — | 1.0x |

---

## Platform Support

| Platform | Counties | Payload Type |
|----------|----------|-------------|
| **CodeRED** | Ventura, Santa Barbara, San Luis Obispo | GeoNotification — voice, SMS, email, TDD, Spanish |
| **Everbridge** | Los Angeles, San Diego, Orange | Mass Notification REST — geo polygon, multi-channel |

---

## Quick Start

```bash
# Clone the repo
git clone https://github.com/Hail15/Firebridge.git
cd Firebridge

# Install dependencies
pip install -r requirements.txt

# Start the server
python -m uvicorn main:app --reload --port 8000
```

Then open [http://localhost:8000/dashboard](http://localhost:8000/dashboard)

---

## Demo

```bash
# Run a Santa Ana wind simulation
curl -X POST "http://localhost:8000/simulate/run?scenario=santa_ana&location=los_angeles"

# Run a Diablo wind simulation
curl -X POST "http://localhost:8000/simulate/run?scenario=diablo&location=ventura"

# Fire a live webhook
python test_webhook.py
```

---

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/dashboard` | GET | Interactive demo dashboard |
| `/map` | GET | Live evacuation zone map |
| `/webhook/pano` | POST | Pano AI detection webhook receiver |
| `/simulate/run` | POST | Run a wind scenario simulation |
| `/simulate/scenarios` | GET | List all available scenarios |
| `/config` | GET | County routing configuration |
| `/health` | GET | Health check |
| `/docs` | GET | Swagger API docs |

---

## Project Structure

```
firebridge/
├── main.py           # FastAPI app, all routes, pipeline orchestration
├── zone_builder.py   # Shapely evacuation polygon generator
├── router.py         # County routing and notification formatter
├── map_builder.py    # Folium interactive map renderer
├── simulator.py      # Wind scenario simulation system
├── dashboard.html    # Demo dashboard UI
├── test_webhook.py   # Local test script
└── requirements.txt  # Dependencies
```

---

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI + Uvicorn |
| Geospatial | GeoPandas, Shapely, Folium |
| Wind Data | NOAA NWS API |
| Notifications | CodeRED GeoNotification, Everbridge REST |
| Maps | Leaflet.js via Folium |

---

## Built By

**Ian Ostrowski**  
Built independently as a proof of concept demonstrating automated integration between Pano AI wildfire detection and mass notification platforms.

---

<div align="center">

*FireBridge v0.1.0 — Not for operational use*

</div>