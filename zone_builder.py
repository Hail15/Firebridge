"""
FireBridge — Zone Builder (Phase 2)
Generates a wind-skewed evacuation zone polygon from a fire detection + wind data.

Logic:
    1. Start with a 2-mile circular buffer around the fire point
    2. Calculate a downwind skew factor based on wind speed (scales with mph)
    3. Use Shapely affinity.scale() to stretch the circle elliptically downwind
    4. Rotate the ellipse to align with wind direction
    5. Return GeoJSON polygon + metadata

Wind skew formula:
    skew_factor = 1.0 + (wind_speed_mph / 20.0)
    - 0 mph  → 1.0x (perfect circle, no skew)
    - 10 mph → 1.5x downwind stretch
    - 20 mph → 2.0x downwind stretch
    - 25 mph → 2.25x downwind stretch  ← our LA County demo case
    - 40 mph → 3.0x downwind stretch

Author: Ian Ostrowski
"""

import math
import json
import logging
from shapely.geometry import Point, mapping
from shapely import affinity

log = logging.getLogger("firebridge.zone_builder")

# ── Constants ──────────────────────────────────────────────────────────────────
BASE_RADIUS_MILES = 2.0
MILES_TO_DEGREES = 1 / 69.0  # Approximate degrees per mile at mid-latitudes


def build_evacuation_zone(
    latitude: float,
    longitude: float,
    wind_speed_mph: float,
    wind_direction_degrees: float,
    base_radius_miles: float = BASE_RADIUS_MILES,
) -> dict:
    """
    Build a wind-skewed evacuation zone polygon.

    Args:
        latitude: Fire detection latitude
        longitude: Fire detection longitude
        wind_speed_mph: Current wind speed in mph (from NOAA)
        wind_direction_degrees: Wind FROM direction in degrees (meteorological)
                                0° = wind from North, 90° = wind from East
        base_radius_miles: Base buffer radius before skew (default 2 miles)

    Returns:
        dict with GeoJSON polygon, skew metadata, and zone stats
    """
    log.info(
        f"Building evacuation zone | Origin=({latitude}, {longitude}) | "
        f"Wind={wind_speed_mph} mph from {wind_direction_degrees}° | "
        f"Base radius={base_radius_miles} miles"
    )

    # ── Step 1: Base circular buffer ───────────────────────────────────────────
    fire_point = Point(longitude, latitude)
    base_radius_deg = base_radius_miles * MILES_TO_DEGREES

    # Create circle with enough segments to look smooth on the map
    base_circle = fire_point.buffer(base_radius_deg, resolution=64)

    # ── Step 2: Calculate wind skew factor ────────────────────────────────────
    # Scale with wind speed: adds 5% stretch per mph of wind
    skew_factor = 1.0 + (wind_speed_mph / 20.0)
    skew_factor = min(skew_factor, 4.0)  # Cap at 4x for extreme wind events

    log.info(f"Wind skew factor: {skew_factor:.2f}x (wind={wind_speed_mph} mph)")

    # ── Step 3: Stretch ellipse downwind ──────────────────────────────────────
    # Scale Y axis (north-south) by skew_factor to create an ellipse
    # We'll rotate it to match wind direction in the next step
    ellipse = affinity.scale(base_circle, xfact=1.0, yfact=skew_factor, origin=fire_point)

    # ── Step 4: Rotate to align with wind direction ────────────────────────────
    # Meteorological wind direction = direction wind is FROM
    # We want to stretch DOWNWIND = opposite direction
    # Shapely rotation is counter-clockwise from East (geographic)
    # Convert: downwind_direction = wind_from + 180°
    downwind_direction = (wind_direction_degrees + 180) % 360

    # Convert meteorological bearing to Shapely rotation angle
    # Meteorological: 0° = North, clockwise
    # Shapely: 0° = East, counter-clockwise
    rotation_angle = 90 - downwind_direction

    zone_polygon = affinity.rotate(
        ellipse,
        angle=rotation_angle,
        origin=fire_point,
        use_radians=False,
    )

    log.info(
        f"Polygon generated | Downwind direction={downwind_direction}° | "
        f"Rotation angle={rotation_angle}° | "
        f"Area={zone_polygon.area:.6f} sq degrees"
    )

    # ── Step 5: Calculate human-readable zone stats ────────────────────────────
    # Approximate area in square miles
    area_sq_miles = zone_polygon.area / (MILES_TO_DEGREES ** 2)

    # Bounding box for map fitting
    bounds = zone_polygon.bounds  # (minx, miny, maxx, maxy) = (W, S, E, N)

    # Downwind tip coordinate (furthest point in downwind direction)
    downwind_tip = _get_downwind_tip(zone_polygon, downwind_direction, latitude, longitude)

    # ── Step 6: Build output ───────────────────────────────────────────────────
    geojson_polygon = mapping(zone_polygon)

    result = {
        "type": "evacuation_zone",
        "geojson": {
            "type": "Feature",
            "geometry": geojson_polygon,
            "properties": {
                "fire_lat": latitude,
                "fire_lon": longitude,
                "base_radius_miles": base_radius_miles,
                "wind_speed_mph": wind_speed_mph,
                "wind_direction_degrees": wind_direction_degrees,
                "downwind_direction_degrees": downwind_direction,
                "skew_factor": round(skew_factor, 2),
                "area_sq_miles": round(area_sq_miles, 2),
            },
        },
        "stats": {
            "base_radius_miles": base_radius_miles,
            "skew_factor": round(skew_factor, 2),
            "area_sq_miles": round(area_sq_miles, 2),
            "downwind_direction_degrees": downwind_direction,
            "downwind_tip_lat": downwind_tip[1],
            "downwind_tip_lon": downwind_tip[0],
            "bounds": {
                "west": round(bounds[0], 6),
                "south": round(bounds[1], 6),
                "east": round(bounds[2], 6),
                "north": round(bounds[3], 6),
            },
        },
        "interpretation": _interpret_zone(wind_speed_mph, skew_factor, area_sq_miles),
    }

    log.info(
        f"✅ Zone complete | Area={area_sq_miles:.1f} sq miles | "
        f"Skew={skew_factor:.2f}x | Downwind tip=({downwind_tip[1]:.4f}, {downwind_tip[0]:.4f})"
    )

    return result


def _get_downwind_tip(polygon, downwind_direction_deg: float, origin_lat: float, origin_lon: float):
    """Find the coordinate of the polygon furthest in the downwind direction."""
    coords = list(polygon.exterior.coords)

    # Convert downwind bearing to unit vector
    bearing_rad = math.radians(downwind_direction_deg)
    dx = math.sin(bearing_rad)
    dy = math.cos(bearing_rad)

    # Find point with maximum projection onto downwind vector
    best_coord = max(
        coords,
        key=lambda c: (c[0] - origin_lon) * dx + (c[1] - origin_lat) * dy,
    )
    return best_coord


def _interpret_zone(wind_speed_mph: float, skew_factor: float, area_sq_miles: float) -> str:
    """Generate a human-readable interpretation of the zone for the notification payload."""
    if wind_speed_mph < 5:
        wind_desc = "calm winds — symmetric evacuation zone"
    elif wind_speed_mph < 15:
        wind_desc = f"light winds ({wind_speed_mph} mph) — slight downwind expansion"
    elif wind_speed_mph < 25:
        wind_desc = f"moderate winds ({wind_speed_mph} mph) — significant downwind expansion"
    else:
        wind_desc = f"strong winds ({wind_speed_mph} mph) — aggressive downwind expansion"

    return (
        f"{wind_desc}. Zone covers approximately {area_sq_miles:.1f} sq miles "
        f"({skew_factor:.1f}x base radius downwind). Immediate evacuation recommended."
    )


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("\n" + "="*60)
    print("  FireBridge Zone Builder — Standalone Test")
    print("="*60)

    # Simulate the LA County detection with real NOAA wind data we got in Phase 1
    result = build_evacuation_zone(
        latitude=34.0522,
        longitude=-118.2437,
        wind_speed_mph=25,
        wind_direction_degrees=157.5,  # SSE — from our live NOAA pull
    )

    print("\n📊 Zone Stats:")
    for k, v in result["stats"].items():
        if k != "bounds":
            print(f"   {k}: {v}")
    print(f"   bounds: {result['stats']['bounds']}")

    print(f"\n📝 Interpretation:")
    print(f"   {result['interpretation']}")

    print(f"\n🗺️  GeoJSON (truncated):")
    coords = result["geojson"]["geometry"]["coordinates"][0]
    print(f"   Polygon with {len(coords)} coordinate points")
    print(f"   First coord: {coords[0]}")
    print(f"   Last coord:  {coords[-1]}")

    print("\n✅ Zone builder working — ready for Phase 3 (routing + notification)")
    print("="*60 + "\n")