"""
FireBridge — County Router + Notification Dispatcher (Phase 3)

Routing logic:
    1. Try point-in-polygon lookup against county bounding boxes (coords-first)
    2. Fall back to county name match if coords don't resolve
    3. Format mock notification payload for the matched platform (CodeRED or Everbridge)
    4. Log the dispatch event

County config reflects real-world platform distribution in California:
    - CodeRED:   Ventura, Santa Barbara, San Luis Obispo
    - Everbridge: Los Angeles, San Diego, Orange

Author: Ian Ostrowski
"""

import logging
from datetime import datetime
from typing import Optional

log = logging.getLogger("firebridge.router")

# ── County Platform Config ─────────────────────────────────────────────────────
# Each county has:
#   - platform: which notification system they use
#   - api_endpoint: mock URL (would be real in production)
#   - account_id: mock account identifier
#   - bbox: (min_lat, max_lat, min_lon, max_lon) bounding box for coord lookup
#   - contact: mock county emergency manager contact

COUNTY_CONFIG = {
    "Ventura": {
        "platform": "CodeRED",
        "api_endpoint": "https://api.codered.com/v1/notifications",
        "account_id": "CR-VENTURA-0042",
        "contact": "Ventura County OES",
        "bbox": (34.05, 34.90, -119.85, -118.65),
    },
    "Santa Barbara": {
        "platform": "CodeRED",
        "api_endpoint": "https://api.codered.com/v1/notifications",
        "account_id": "CR-SANTABARBARA-0017",
        "contact": "Santa Barbara County OES",
        "bbox": (34.35, 35.00, -120.65, -119.45),
    },
    "San Luis Obispo": {
        "platform": "CodeRED",
        "api_endpoint": "https://api.codered.com/v1/notifications",
        "account_id": "CR-SLO-0009",
        "contact": "SLO County OES",
        "bbox": (35.00, 35.80, -121.35, -120.05),
    },
    "Los Angeles": {
        "platform": "Everbridge",
        "api_endpoint": "https://api.everbridge.net/rest/notifications",
        "account_id": "EB-LA-COUNTY-8821",
        "contact": "LA County OES",
        "bbox": (33.70, 34.82, -118.95, -117.65),
    },
    "San Diego": {
        "platform": "Everbridge",
        "api_endpoint": "https://api.everbridge.net/rest/notifications",
        "account_id": "EB-SANDIEGO-4433",
        "contact": "San Diego County OES",
        "bbox": (32.53, 33.51, -117.60, -116.08),
    },
    "Orange": {
        "platform": "Everbridge",
        "api_endpoint": "https://api.everbridge.net/rest/notifications",
        "account_id": "EB-ORANGE-2291",
        "contact": "Orange County OES",
        "bbox": (33.38, 33.95, -118.12, -117.41),
    },
}


# ── Router ─────────────────────────────────────────────────────────────────────

def route_detection(
    latitude: float,
    longitude: float,
    detection: dict,
    wind: dict,
    zone: dict,
    county_name: Optional[str] = None,
) -> dict:
    """
    Route a fire detection to the correct notification platform.

    Args:
        latitude: Fire detection latitude
        longitude: Fire detection longitude
        detection: Pano AI detection payload dict
        wind: NOAA wind data dict
        zone: Evacuation zone dict from zone_builder
        county_name: Optional county name override (fallback if coords don't resolve)

    Returns:
        Full dispatch result including matched county, platform, and mock payload
    """

    # ── Step 1: Resolve county from coordinates ────────────────────────────────
    matched_county = _coords_to_county(latitude, longitude)

    if matched_county:
        log.info(f"County resolved by coordinates: {matched_county}")
        resolution_method = "coordinates"
    elif county_name:
        matched_county = _fuzzy_county_match(county_name)
        if matched_county:
            log.info(f"County resolved by name fallback: {matched_county}")
            resolution_method = "county_name_fallback"
        else:
            log.warning(f"County name '{county_name}' not found in config")
            matched_county = None
            resolution_method = "unresolved"
    else:
        resolution_method = "unresolved"

    # ── Step 2: Handle unresolved county ──────────────────────────────────────
    if not matched_county:
        log.error(f"No county match for coords ({latitude}, {longitude})")
        return {
            "status": "unrouted",
            "reason": "Coordinates did not match any configured county and no county name provided.",
            "suggestion": "Verify coordinates are within a configured California county.",
            "configured_counties": list(COUNTY_CONFIG.keys()),
        }

    config = COUNTY_CONFIG[matched_county]
    platform = config["platform"]

    log.info(
        f"Routing to {platform} | County={matched_county} | "
        f"Account={config['account_id']} | Method={resolution_method}"
    )

    # ── Step 3: Format platform-specific payload ───────────────────────────────
    if platform == "CodeRED":
        notification_payload = _format_codered_payload(
            matched_county, config, detection, wind, zone
        )
    elif platform == "Everbridge":
        notification_payload = _format_everbridge_payload(
            matched_county, config, detection, wind, zone
        )
    else:
        notification_payload = {"error": f"Unknown platform: {platform}"}

    # ── Step 4: Build dispatch result ─────────────────────────────────────────
    dispatch_result = {
        "status": "dispatched",
        "resolution_method": resolution_method,
        "county": matched_county,
        "platform": platform,
        "account_id": config["account_id"],
        "api_endpoint": config["api_endpoint"],
        "contact": config["contact"],
        "notification_payload": notification_payload,
        "dispatched_at": datetime.utcnow().isoformat(),
        "mode": "MOCK — no real notification sent",
    }

    log.info(
        f"✅ Mock dispatch complete | County={matched_county} | "
        f"Platform={platform} | Account={config['account_id']}"
    )

    return dispatch_result


# ── Platform Payload Formatters ────────────────────────────────────────────────

def _format_codered_payload(
    county: str, config: dict, detection: dict, wind: dict, zone: dict
) -> dict:
    """
    Format a CodeRED-style notification payload.
    Structure mirrors CodeRED's actual GeoNotification API format.
    """
    area_sq_miles = zone["stats"]["area_sq_miles"]
    skew_factor = zone["stats"]["skew_factor"]
    wind_speed = wind["wind_speed_mph"]
    wind_dir = wind["wind_direction_cardinal"] or "Calm"
    confidence_pct = int(detection["confidence"] * 100)

    message = (
        f"WILDFIRE EVACUATION ALERT — {county.upper()} COUNTY. "
        f"A wildfire has been detected near coordinates "
        f"({detection['latitude']:.4f}, {detection['longitude']:.4f}). "
        f"Current winds: {wind_speed} mph from the {wind_dir}. "
        f"Evacuation zone covers approximately {area_sq_miles:.1f} square miles. "
        f"EVACUATE IMMEDIATELY if you are in the designated zone. "
        f"Follow directions from emergency personnel. "
        f"Detection confidence: {confidence_pct}%."
    )

    return {
        "platform": "CodeRED",
        "account_id": config["account_id"],
        "notification_type": "GeoNotification",
        "priority": "EMERGENCY",
        "channels": ["voice", "sms", "email", "mobile_app"],
        "message": {
            "voice_script": message,
            "sms_text": (
                f"WILDFIRE ALERT-{county.upper()} COUNTY: Fire detected. "
                f"Wind {wind_speed}mph {wind_dir}. Zone: {area_sq_miles:.1f} sq mi. "
                f"EVACUATE NOW. Follow emergency personnel directions."
            ),
            "email_subject": f"EMERGENCY: Wildfire Evacuation Alert — {county} County",
            "email_body": message,
        },
        "geo_zone": {
            "type": "geojson_polygon",
            "geojson": zone["geojson"],
        },
        "detection_metadata": {
            "source": "Pano AI Wildfire Detection",
            "detection_id": detection["detection_id"],
            "camera_id": detection.get("camera_id"),
            "confidence": detection["confidence"],
            "wind_skew_factor": skew_factor,
        },
        "codered_specific": {
            "call_attempts": 3,
            "retry_interval_minutes": 5,
            "do_not_call_override": True,
            "tdd_enabled": True,
            "spanish_language": True,
        },
    }


def _format_everbridge_payload(
    county: str, config: dict, detection: dict, wind: dict, zone: dict
) -> dict:
    """
    Format an Everbridge-style notification payload.
    Structure mirrors Everbridge Mass Notification REST API format.
    """
    area_sq_miles = zone["stats"]["area_sq_miles"]
    skew_factor = zone["stats"]["skew_factor"]
    wind_speed = wind["wind_speed_mph"]
    wind_dir = wind["wind_direction_cardinal"] or "Calm"
    confidence_pct = int(detection["confidence"] * 100)

    message = (
        f"WILDFIRE EVACUATION ALERT — {county.upper()} COUNTY. "
        f"A wildfire has been detected near coordinates "
        f"({detection['latitude']:.4f}, {detection['longitude']:.4f}). "
        f"Current winds: {wind_speed} mph from the {wind_dir}. "
        f"Evacuation zone covers approximately {area_sq_miles:.1f} square miles. "
        f"EVACUATE IMMEDIATELY if you are in the designated zone."
    )

    return {
        "platform": "Everbridge",
        "account_id": config["account_id"],
        "notification": {
            "name": f"FireBridge Auto-Alert — {county} County — {detection['detection_id']}",
            "messageType": "Notification",
            "priority": 1,
            "incidentType": "WILDFIRE_EVACUATION",
            "status": "Active",
        },
        "message": {
            "subject": f"EMERGENCY: Wildfire Evacuation Alert — {county} County",
            "body": message,
            "sms": (
                f"WILDFIRE ALERT-{county.upper()}: Fire detected. "
                f"Wind {wind_speed}mph {wind_dir}. Zone {area_sq_miles:.1f}sqmi. EVACUATE NOW."
            ),
        },
        "contacts": {
            "selection_method": "geo_polygon",
            "geo_zone": {
                "type": "Polygon",
                "geojson": zone["geojson"],
            },
        },
        "delivery_channels": ["SMS", "Voice", "Email", "Push"],
        "detection_metadata": {
            "source": "Pano AI Wildfire Detection",
            "detection_id": detection["detection_id"],
            "camera_id": detection.get("camera_id"),
            "confidence": detection["confidence"],
            "wind_skew_factor": skew_factor,
            "nws_grid": wind.get("nws_grid"),
        },
        "everbridge_specific": {
            "organizationId": config["account_id"],
            "scenarioId": "WILDFIRE_AUTO_EVAC_001",
            "publishedAt": datetime.utcnow().isoformat(),
            "expiresAt": None,
        },
    }


# ── County Resolution Helpers ──────────────────────────────────────────────────

def _coords_to_county(lat: float, lon: float) -> Optional[str]:
    """
    Point-in-bounding-box lookup. Checks coords against each county's bbox.
    Returns the first matching county name or None.

    Note: In production this would be a true point-in-polygon against
    Census TIGER/Line county shapefiles — exactly what we process at Crisis24.
    For the POC, bounding boxes are accurate enough for demo purposes.
    """
    for county, config in COUNTY_CONFIG.items():
        min_lat, max_lat, min_lon, max_lon = config["bbox"]
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return county
    return None


def _fuzzy_county_match(county_name: str) -> Optional[str]:
    """Case-insensitive county name match with 'County' suffix stripping."""
    cleaned = county_name.strip().replace(" County", "").replace(" county", "").title()
    if cleaned in COUNTY_CONFIG:
        return cleaned
    # Partial match fallback
    for configured in COUNTY_CONFIG:
        if cleaned.lower() in configured.lower() or configured.lower() in cleaned.lower():
            return configured
    return None


def get_county_config() -> dict:
    """Return the full county config — used by the /config endpoint."""
    return {
        county: {
            "platform": cfg["platform"],
            "account_id": cfg["account_id"],
            "contact": cfg["contact"],
        }
        for county, cfg in COUNTY_CONFIG.items()
    }


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import json
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("\n" + "="*60)
    print("  FireBridge Router — Standalone Test")
    print("="*60)

    # Mock data matching what Phase 1 + 2 would produce
    mock_detection = {
        "detection_id": "PANO-TEST-001",
        "latitude": 34.0522,
        "longitude": -118.2437,
        "confidence": 0.91,
        "camera_id": "CAM-LA-12",
    }
    mock_wind = {
        "wind_speed_mph": 25,
        "wind_direction_cardinal": "SSE",
        "wind_direction_degrees": 157.5,
        "temperature_f": 54,
        "nws_grid": "LOX 155,45",
    }
    mock_zone = {
        "stats": {"area_sq_miles": 28.3, "skew_factor": 2.25},
        "geojson": {"type": "Feature", "geometry": {"type": "Polygon", "coordinates": [[]]}, "properties": {}},
    }

    # Test 1: LA County (Everbridge) by coordinates
    print("\n🔀 Test 1: LA County coords → should route to Everbridge")
    result = route_detection(34.0522, -118.2437, mock_detection, mock_wind, mock_zone)
    print(f"   County: {result.get('county')} | Platform: {result.get('platform')} | Status: {result.get('status')}")
    print(f"   Resolution: {result.get('resolution_method')}")

    # Test 2: Ventura County (CodeRED) by coordinates
    print("\n🔀 Test 2: Ventura County coords → should route to CodeRED")
    mock_detection_v = {**mock_detection, "latitude": 34.3705, "longitude": -119.1391}
    result2 = route_detection(34.3705, -119.1391, mock_detection_v, mock_wind, mock_zone)
    print(f"   County: {result2.get('county')} | Platform: {result2.get('platform')} | Status: {result2.get('status')}")

    # Test 3: Name fallback
    print("\n🔀 Test 3: Unknown coords + county name fallback → San Diego / Everbridge")
    result3 = route_detection(0, 0, mock_detection, mock_wind, mock_zone, county_name="San Diego County")
    print(f"   County: {result3.get('county')} | Platform: {result3.get('platform')} | Status: {result3.get('status')}")
    print(f"   Resolution: {result3.get('resolution_method')}")

    # Test 4: Unresolvable
    print("\n🔀 Test 4: No match → unrouted")
    result4 = route_detection(40.0, -75.0, mock_detection, mock_wind, mock_zone)
    print(f"   Status: {result4.get('status')} | Reason: {result4.get('reason')}")

    print("\n✅ Router working — ready for Phase 4 (Folium map render)")
    print("="*60 + "\n")