# 🔥 FireBridge

**Pano AI Wildfire Detection → Mass Notification Middleware**
*Ian Ostrowski — Pano AI Partnership Pitch*

---

## What It Does

FireBridge is a middleware layer that sits between Pano AI's wildfire camera detection system and mass notification platforms (CodeRED, Everbridge). The moment a camera detects smoke, FireBridge automatically:

1. **Receives** the Pano AI detection webhook (GPS coordinates + confidence score)
2. **Pulls** real-time wind data from the NOAA NWS free API (no key required)
3. **Calculates** a wind-skewed GeoJSON evacuation zone polygon using Shapely — stretches downwind based on actual wind speed
4. **Routes** to the correct notification platform based on GPS coordinates → county lookup (CodeRED or Everbridge)
5. **Formats** a complete mock notification payload (voice script, SMS, email, push)
6. **Renders** an interactive Folium map showing the fire point, evacuation zone, wind data, and dispatch log
7. **Exposes** everything via a live public URL through ngrok for remote demo access

---

## Project Structure

```
FireBridge/
├── main.py            ← FastAPI app — all routes and pipeline orchestration
├── zone_builder.py    ← Shapely evacuation zone polygon generator
├── router.py          ← County → platform routing + notification formatter
├── map_builder.py     ← Folium interactive map renderer
├── simulator.py       ← Wind scenario simulator for demo use
├── dashboard.html     ← Polished demo dashboard (use this for the pitch)
├── test_webhook.py    ← Local test script
├── requirements.txt   ← Python dependencies
├── README.md          ← This file
└── .vscode/
    └── launch.json    ← VS Code run configurations
```

---

## Quick Start

### 1. Install dependencies
```bash
~/.pyenv/versions/3.12.3/bin/pip install -r requirements.txt
```

### 2. Start the server
```bash
~/.pyenv/versions/3.12.3/bin/python -m uvicorn main:app --reload --port 8000
```

### 3. Open the API docs
```
http://localhost:8000/docs
```

### 4. Expose publicly via ngrok (optional)
```bash
ngrok http 8000
```

---

## API Endpoints

### Health
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Service info |
| GET | `/health` | Health check |

### Webhook
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/webhook/pano-detection` | Main Pano AI webhook receiver |
| POST | `/webhook/test` | Quick test — LA County, live NOAA data |

### Map
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/map` | Latest generated interactive HTML map |

### Config
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/config` | County → platform routing table |

### Dashboard
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dashboard` | Polished demo control panel — use this for the Pano AI pitch |

### Simulation
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/simulate/scenarios` | List all wind scenarios and demo locations |
| POST | `/simulate/run` | Run a named wind scenario — bypasses live NOAA |

---

## Wind Simulation Scenarios

Use POST /simulate/run with scenario and location query parameters.

| Scenario | Speed | Direction | Skew | Description |
|----------|-------|-----------|------|-------------|
| santa_ana | 35 mph | NE (045°) | 2.75x | Classic SoCal fire weather |
| diablo | 40 mph | NE (045°) | 3.0x | NorCal offshore winds |
| onshore_marine | 15 mph | W (270°) | 1.75x | Coastal sea breeze |
| calm | 0 mph | — | 1.0x | Symmetric baseline circle |

| Location | Coordinates | Platform | Account |
|----------|-------------|----------|---------|
| los_angeles | 34.0522, -118.2437 | Everbridge | EB-LA-COUNTY-8821 |
| ventura | 34.3705, -119.1391 | CodeRED | CR-VENTURA-0042 |

---

## County Routing Config

6 California counties pre-configured across two platforms:

| County | Platform | Account ID |
|--------|----------|------------|
| Los Angeles | Everbridge | EB-LA-COUNTY-8821 |
| San Diego | Everbridge | EB-SANDIEGO-4433 |
| Orange | Everbridge | EB-ORANGE-2291 |
| Ventura | CodeRED | CR-VENTURA-0042 |
| Santa Barbara | CodeRED | CR-SANTABARBARA-0017 |
| San Luis Obispo | CodeRED | CR-SLO-0009 |

Routing is coordinates-first (bounding box lookup), with county name fallback.
In production this would use Census TIGER/Line shapefiles for true point-in-polygon.

---

## Wind Skew Formula

```
skew_factor = 1.0 + (wind_speed_mph / 20.0)
```

| Wind Speed | Skew Factor | Zone Area (from 2mi base) |
|------------|-------------|---------------------------|
| 0 mph | 1.0x | ~12.6 sq miles |
| 15 mph | 1.75x | ~22.1 sq miles |
| 35 mph | 2.75x | ~34.6 sq miles |
| 40 mph | 3.0x | ~37.7 sq miles |

The polygon stretches elliptically downwind using shapely.affinity.scale() and shapely.affinity.rotate().

---

## Demo Flow (Pano AI Pitch)

Run these in order for maximum impact during the demo:

**Open the dashboard first**
```
http://localhost:8000/dashboard
```
Or over ngrok for remote access. All simulations run from here — no Swagger UI needed.

**Step 1 — Baseline**
POST /simulate/run?scenario=calm&location=los_angeles
Show the symmetric 12.6 sq mile circle — "This is what a zero-wind scenario looks like."

**Step 2 — Santa Ana**
POST /simulate/run?scenario=santa_ana&location=ventura
Zone jumps to 34.6 sq miles, stretches SW, routes to CodeRED.
"35 mph Santa Ana winds — the zone nearly triples and routes automatically to CodeRED."

**Step 3 — Platform switch**
POST /simulate/run?scenario=diablo&location=los_angeles
Same wind intensity, different county — automatically routes to Everbridge instead.
"FireBridge knows which platform each county uses — zero manual configuration."

**Step 4 — Open the map after each run**
GET /map
The map updates live after every simulation.

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| API Framework | FastAPI + Uvicorn |
| Wind Data | NOAA NWS Free API (no key required) |
| Geospatial | GeoPandas, Shapely |
| Map Rendering | Folium + Leaflet.js |
| Public Exposure | ngrok |
| Language | Python 3.12.3 |

---

## Pipeline Architecture

```
[Pano AI Camera]
      ↓
[POST /webhook/pano-detection]
      ↓
[Confidence Gate] ── < 50% → flagged, not dispatched
      ↓
[NOAA Wind API] ── coordinates → NWS grid → hourly forecast
      ↓
[Zone Builder] ── base circle + wind skew + rotation → GeoJSON polygon
      ↓
[County Router] ── GPS coords → county bbox → platform config
      ↓
[Notification Formatter] ── CodeRED or Everbridge payload
      ↓
[Map Builder] ── Folium HTML map → /map endpoint
      ↓
[Response] ── full enriched event JSON
```

---

## Notes

- NOAA API is free, no key required, CONUS coverage only
- Confidence threshold: detections below 50% are flagged and held
- ngrok free tier URL changes on every restart — regenerate before each demo session
- Map file (firebridge_map.html) is overwritten on every detection — always shows latest event
- All notifications are MOCK — no real alerts are sent
- This is a POC — production would require real API credentials, TIGER/Line shapefile polygon routing, and infrastructure hardening

---

*Ian Ostrowski — Not for operational use*