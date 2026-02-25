"""
FireBridge — Pano AI to Mass Notification Middleware
Phase 1: FastAPI Webhook Listener + NOAA Wind Data Pull

Author: Ian Ostrowski
Purpose: POC for Pano AI partnership pitch
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from typing import Optional
import requests
import logging
from datetime import datetime
from zone_builder import build_evacuation_zone
from router import route_detection, get_county_config
from map_builder import build_map
from simulator import get_scenario, get_location, list_scenarios, list_locations

# ── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("firebridge.log"),
    ],
)
log = logging.getLogger("firebridge")

# ── App ────────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="FireBridge",
    description="Pano AI wildfire detection → mass notification middleware",
    version="0.1.0",
)

# ── Pano AI Webhook Schema ─────────────────────────────────────────────────────
class PanoDetectionPayload(BaseModel):
    """
    Simulated Pano AI wildfire detection webhook payload.
    Real Pano payloads include camera ID, pan/tilt angle, and image URL —
    we're abstracting to the derived GPS + confidence for this POC.
    """
    detection_id: str = Field(..., example="PANO-2024-00142")
    latitude: float = Field(..., ge=-90, le=90, example=34.2521)
    longitude: float = Field(..., ge=-180, le=180, example=-119.7534)
    confidence: float = Field(..., ge=0.0, le=1.0, example=0.91)
    camera_id: Optional[str] = Field(None, example="CAM-VENTURA-07")
    detected_at: Optional[str] = Field(
        default_factory=lambda: datetime.utcnow().isoformat(),
        example="2024-07-15T18:42:00Z",
    )
    notes: Optional[str] = Field(None, example="Smoke plume visible, NW quadrant")


# ── NOAA Wind Data ─────────────────────────────────────────────────────────────
NOAA_POINTS_URL = "https://api.weather.gov/points/{lat},{lon}"
NOAA_HEADERS = {
    "User-Agent": "FireBridge/0.1 (Ian Ostrowski POC; contact@crisis24.com)",
    "Accept": "application/geo+json",
}

def get_noaa_wind(lat: float, lon: float) -> dict:
    """
    Pull current wind speed + direction from NOAA Weather API (free, no key required).

    Flow:
        1. /points/{lat},{lon}  → resolves to nearest NWS office + gridpoint
        2. /gridpoints/{office}/{x},{y}/forecast/hourly → grab the first period
    """
    # Step 1: Resolve coordinates to NWS gridpoint
    points_url = NOAA_POINTS_URL.format(lat=round(lat, 4), lon=round(lon, 4))
    log.info(f"NOAA points lookup: {points_url}")

    try:
        r = requests.get(points_url, headers=NOAA_HEADERS, timeout=10)
        r.raise_for_status()
    except requests.RequestException as e:
        log.error(f"NOAA points lookup failed: {e}")
        raise HTTPException(status_code=502, detail=f"NOAA points API error: {e}")

    props = r.json().get("properties", {})
    forecast_hourly_url = props.get("forecastHourly")
    grid_id = props.get("gridId")
    grid_x = props.get("gridX")
    grid_y = props.get("gridY")

    if not forecast_hourly_url:
        log.error("NOAA response missing forecastHourly URL")
        raise HTTPException(status_code=502, detail="NOAA did not return a forecastHourly URL — coordinates may be outside CONUS coverage.")

    log.info(f"NWS Grid: {grid_id} ({grid_x},{grid_y}) → {forecast_hourly_url}")

    # Step 2: Pull hourly forecast, grab first period (current conditions)
    try:
        r2 = requests.get(forecast_hourly_url, headers=NOAA_HEADERS, timeout=10)
        r2.raise_for_status()
    except requests.RequestException as e:
        log.error(f"NOAA hourly forecast failed: {e}")
        raise HTTPException(status_code=502, detail=f"NOAA hourly forecast error: {e}")

    periods = r2.json().get("properties", {}).get("periods", [])
    if not periods:
        raise HTTPException(status_code=502, detail="NOAA returned no forecast periods.")

    current = periods[0]

    wind_data = {
        "wind_speed_mph": _parse_wind_speed(current.get("windSpeed", "0 mph")),
        "wind_direction_cardinal": current.get("windDirection", "N"),
        "wind_direction_degrees": _cardinal_to_degrees(current.get("windDirection", "N")),
        "temperature_f": current.get("temperature"),
        "short_forecast": current.get("shortForecast"),
        "forecast_time": current.get("startTime"),
        "nws_grid": f"{grid_id} {grid_x},{grid_y}",
        "source": "NOAA NWS Hourly Forecast API",
    }

    log.info(
        f"Wind data → {wind_data['wind_speed_mph']} mph from "
        f"{wind_data['wind_direction_cardinal']} ({wind_data['wind_direction_degrees']}°)"
    )
    return wind_data


def _parse_wind_speed(wind_str: str) -> float:
    """Extract numeric mph value from NOAA string like '12 mph' or '5 to 10 mph'."""
    import re
    nums = re.findall(r"\d+", wind_str)
    if not nums:
        return 0.0
    if len(nums) == 1:
        return float(nums[0])
    # Range like "5 to 10 mph" — use average
    return (float(nums[0]) + float(nums[1])) / 2


def _cardinal_to_degrees(cardinal: str) -> float:
    """Convert cardinal/intercardinal wind direction to degrees (meteorological)."""
    mapping = {
        "N": 0, "NNE": 22.5, "NE": 45, "ENE": 67.5,
        "E": 90, "ESE": 112.5, "SE": 135, "SSE": 157.5,
        "S": 180, "SSW": 202.5, "SW": 225, "WSW": 247.5,
        "W": 270, "WNW": 292.5, "NW": 315, "NNW": 337.5,
    }
    return mapping.get(cardinal.upper(), 0.0)


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Health"])
def root():
    return {
        "service": "FireBridge",
        "status": "online",
        "version": "0.1.0",
        "description": "Pano AI wildfire → mass notification middleware POC",
    }


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}


@app.post("/webhook/pano-detection", tags=["Webhook"])
def receive_pano_detection(payload: PanoDetectionPayload):
    """
    Primary entry point — receives a Pano AI wildfire detection event.

    Pipeline (Phase 1):
        [Pano Webhook] → [NOAA Wind Pull] → [Return enriched event]

    Future phases will add:
        → [Evacuation Zone Polygon] → [County Router] → [Notification Dispatch] → [Map Render]
    """
    log.info(
        f"🔥 Detection received | ID={payload.detection_id} | "
        f"Coords=({payload.latitude}, {payload.longitude}) | "
        f"Confidence={payload.confidence:.0%} | Camera={payload.camera_id}"
    )

    # Confidence gate — below 0.5 we log and skip notification pipeline
    if payload.confidence < 0.5:
        log.warning(f"Low-confidence detection ({payload.confidence:.0%}) — flagged, not dispatched.")
        return JSONResponse(
            status_code=202,
            content={
                "status": "flagged",
                "reason": f"Confidence {payload.confidence:.0%} below 50% threshold.",
                "detection_id": payload.detection_id,
            },
        )

    # Pull NOAA wind data
    wind = get_noaa_wind(payload.latitude, payload.longitude)

    # Build evacuation zone polygon
    zone = build_evacuation_zone(
        latitude=payload.latitude,
        longitude=payload.longitude,
        wind_speed_mph=wind["wind_speed_mph"],
        wind_direction_degrees=wind["wind_direction_degrees"],
    )

    # Route to correct notification platform
    dispatch = route_detection(
        latitude=payload.latitude,
        longitude=payload.longitude,
        detection=payload.model_dump(),
        wind=wind,
        zone=zone,
    )

    # Build enriched event object
    enriched_event = {
        "status": "accepted",
        "detection": payload.model_dump(),
        "wind": wind,
        "evacuation_zone": zone,
        "dispatch": dispatch,
        "pipeline_stage": "phase_3_complete",
        "next_stage": "map_render",
        "timestamp_processed": datetime.utcnow().isoformat(),
    }

    # Build map
    map_path = build_map(payload.model_dump(), wind, zone, dispatch)

    enriched_event["map_file"] = map_path
    enriched_event["map_url"] = "http://localhost:8000/map"

    log.info(
        f"✅ Pipeline complete | Wind: {wind['wind_speed_mph']} mph from "
        f"{wind['wind_direction_cardinal']} | Zone: {zone['stats']['area_sq_miles']} sq miles | "
        f"Platform: {dispatch.get('platform', 'unrouted')} | County: {dispatch.get('county', 'unknown')} | "
        f"Map: {map_path}"
    )

    return enriched_event


@app.get("/map", tags=["Map"])
def get_map():
    """Returns the latest generated FireBridge map as an interactive HTML file."""
    import os
    if not os.path.exists("firebridge_map.html"):
        return JSONResponse(
            status_code=404,
            content={"detail": "No map generated yet. Fire a detection first via POST /webhook/pano-detection or POST /webhook/test"}
        )
    return FileResponse("firebridge_map.html", media_type="text/html")


@app.post("/webhook/test", tags=["Webhook"])
def test_webhook():
    """
    Fire a simulated Pano AI detection using Ventura County coordinates
    (Thomas Fire area) — useful for quick demo without a real Pano feed.
    """
    test_payload = PanoDetectionPayload(
        detection_id="PANO-TEST-001",
        latitude=34.0522,
        longitude=-118.2437,
        confidence=0.91,
        camera_id="CAM-VENTURA-07",
        detected_at=datetime.utcnow().isoformat(),
        notes="Test detection — Los Angeles County, CA (Everbridge demo scenario)",
    )
    return receive_pano_detection(test_payload)


@app.get("/config", tags=["Config"])
def get_config():
    """Returns the county → platform routing config. Useful for demo overview."""
    return {
        "county_routing": get_county_config(),
        "platforms": ["CodeRED", "Everbridge"],
        "total_counties": 6,
        "routing_method": "coordinates_first_then_county_name_fallback",
    }


# ── Simulation Endpoints ───────────────────────────────────────────────────────

@app.get("/simulate/scenarios", tags=["Simulation"])
def get_scenarios():
    """
    List all available wind scenarios for the demo.
    Use scenario names in POST /simulate/run.
    """
    return {
        "scenarios": list_scenarios(),
        "locations": list_locations(),
        "usage": "POST /simulate/run with scenario and location params",
    }


@app.post("/simulate/run", tags=["Simulation"])
def run_simulation(
    scenario: str = "santa_ana",
    location: str = "los_angeles",
    confidence: float = 0.94,
):
    """
    Run a full FireBridge pipeline simulation with a named wind scenario.

    Scenarios: santa_ana, diablo, onshore_marine, calm
    Locations: los_angeles (Everbridge), ventura (CodeRED)

    This bypasses the live NOAA API and uses pre-built wind data —
    perfect for demo use when real winds are calm.
    """
    # Resolve scenario
    wind = get_scenario(scenario)
    if not wind:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scenario: {scenario!r}. Available: {list(list_scenarios().keys())}"
        )

    # Resolve location
    loc = get_location(location)
    if not loc:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown location: {location!r}. Available: {list(list_locations().keys())}"
        )

    lat = loc["latitude"]
    lon = loc["longitude"]

    log.info(
        f"🎮 Simulation | Scenario={scenario} | Location={location} | "
        f"Wind={wind['wind_speed_mph']} mph from {wind['wind_direction_cardinal']}"
    )

    # Build simulated detection payload
    sim_detection = {
        "detection_id": f"PANO-SIM-{scenario.upper()}-{location.upper()[:2]}",
        "latitude": lat,
        "longitude": lon,
        "confidence": confidence,
        "camera_id": f"CAM-{location.upper()[:3]}-SIM",
        "detected_at": datetime.utcnow().isoformat(),
        "notes": f"Simulated detection — {wind['name']} scenario at {loc['name']}",
    }

    # Build evacuation zone with simulated wind
    zone = build_evacuation_zone(
        latitude=lat,
        longitude=lon,
        wind_speed_mph=wind["wind_speed_mph"],
        wind_direction_degrees=wind["wind_direction_degrees"],
    )

    # Route to correct platform
    dispatch = route_detection(
        latitude=lat,
        longitude=lon,
        detection=sim_detection,
        wind=wind,
        zone=zone,
    )

    # Build map
    map_path = build_map(sim_detection, wind, zone, dispatch)

    result = {
        "status": "simulation_complete",
        "scenario": {
            "id": scenario,
            "name": wind["name"],
            "description": wind["description"],
        },
        "location": {
            "id": location,
            "name": loc["name"],
            "coordinates": {"lat": lat, "lon": lon},
        },
        "detection": sim_detection,
        "wind": wind,
        "evacuation_zone": {
            "area_sq_miles": zone["stats"]["area_sq_miles"],
            "skew_factor": zone["stats"]["skew_factor"],
            "downwind_direction_degrees": zone["stats"]["downwind_direction_degrees"],
            "interpretation": zone["interpretation"],
        },
        "dispatch": {
            "county": dispatch.get("county"),
            "platform": dispatch.get("platform"),
            "account_id": dispatch.get("account_id"),
            "status": dispatch.get("status"),
            "sms_preview": dispatch.get("notification_payload", {}).get("message", {}).get("sms") or
                           dispatch.get("notification_payload", {}).get("message", {}).get("sms_text"),
        },
        "map_url": "http://localhost:8000/map",
        "map_url_public": "See ngrok URL + /map",
        "pipeline_stage": "simulation_complete",
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "SIMULATION — No real NOAA call, no real notification sent",
    }

    log.info(
        f"✅ Simulation complete | {wind['name']} | {loc['name']} | "
        f"Zone: {zone['stats']['area_sq_miles']} sq mi | "
        f"Platform: {dispatch.get('platform')} | Skew: {zone['stats']['skew_factor']}x"
    )

    return result


@app.get("/dashboard", tags=["Dashboard"], response_class=HTMLResponse)
def get_dashboard():
    """FireBridge polished demo dashboard — use this for the Pano AI pitch."""
    import os
    with open("dashboard.html", "r") as f:
        return HTMLResponse(content=f.read())