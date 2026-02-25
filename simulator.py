"""
FireBridge — Wind Simulator (Bonus Demo Feature)
Pre-built wind scenarios for live demo use.

Scenarios:
    - santa_ana:     35 mph from NE (045°) — classic Southern CA fire weather
    - diablo:        40 mph from NE (045°) — Northern CA equivalent, more extreme
    - onshore_marine: 15 mph from W (270°) — coastal onshore flow, pushes fire east
    - calm:          0 mph — symmetric circle baseline

County locations:
    - los_angeles:  34.0522, -118.2437 → Everbridge
    - ventura:      34.3705, -119.1391 → CodeRED

Author: Crisis24 / CodeRED Boundary Specialist
"""

# ── Wind Scenarios ─────────────────────────────────────────────────────────────
WIND_SCENARIOS = {
    "santa_ana": {
        "name": "Santa Ana Winds",
        "description": "Classic Southern California fire weather — hot, dry offshore flow from the NE. Responsible for some of the most destructive wildfires in CA history including the Thomas Fire and Camp Fire.",
        "wind_speed_mph": 35,
        "wind_direction_degrees": 45,
        "wind_direction_cardinal": "NE",
        "temperature_f": 95,
        "short_forecast": "Hot and Extremely Windy — Critical Fire Weather",
        "nws_grid": "SIMULATED",
        "source": "FireBridge Wind Simulator — Santa Ana Scenario",
    },
    "diablo": {
        "name": "Diablo Winds",
        "description": "Northern California equivalent of Santa Ana winds — strong NE offshore flow. Responsible for the 2017 Tubbs Fire and 2019 Kincade Fire.",
        "wind_speed_mph": 40,
        "wind_direction_degrees": 45,
        "wind_direction_cardinal": "NE",
        "temperature_f": 98,
        "short_forecast": "Extremely Hot and Dangerously Windy — Red Flag Warning",
        "nws_grid": "SIMULATED",
        "source": "FireBridge Wind Simulator — Diablo Scenario",
    },
    "onshore_marine": {
        "name": "Onshore Marine Flow",
        "description": "Typical Southern California sea breeze — cool, moist air pushing inland from the Pacific. Lower fire risk but still pushes fire eastward toward inland communities.",
        "wind_speed_mph": 15,
        "wind_direction_degrees": 270,
        "wind_direction_cardinal": "W",
        "temperature_f": 68,
        "short_forecast": "Partly Cloudy with Sea Breeze",
        "nws_grid": "SIMULATED",
        "source": "FireBridge Wind Simulator — Onshore Marine Scenario",
    },
    "calm": {
        "name": "Calm Conditions",
        "description": "No significant wind — evacuation zone is a symmetric circle. Baseline scenario for comparison.",
        "wind_speed_mph": 0,
        "wind_direction_degrees": 0,
        "wind_direction_cardinal": "Calm",
        "temperature_f": 72,
        "short_forecast": "Clear and Calm",
        "nws_grid": "SIMULATED",
        "source": "FireBridge Wind Simulator — Calm Scenario",
    },
}

# ── County Locations ───────────────────────────────────────────────────────────
DEMO_LOCATIONS = {
    "los_angeles": {
        "name": "Los Angeles County",
        "latitude": 34.0522,
        "longitude": -118.2437,
        "description": "Central LA — routes to Everbridge (EB-LA-COUNTY-8821)",
        "expected_platform": "Everbridge",
    },
    "ventura": {
        "name": "Ventura County",
        "latitude": 34.3705,
        "longitude": -119.1391,
        "description": "Ventura County — routes to CodeRED (CR-VENTURA-0042)",
        "expected_platform": "CodeRED",
    },
}


def get_scenario(scenario_name: str) -> dict:
    """Return a named wind scenario or None if not found."""
    return WIND_SCENARIOS.get(scenario_name.lower())


def get_location(location_name: str) -> dict:
    """Return a named demo location or None if not found."""
    return DEMO_LOCATIONS.get(location_name.lower())


def list_scenarios() -> dict:
    """Return all available scenarios for the /simulate/scenarios endpoint."""
    return {
        name: {
            "name": s["name"],
            "description": s["description"],
            "wind_speed_mph": s["wind_speed_mph"],
            "wind_direction_cardinal": s["wind_direction_cardinal"],
            "wind_direction_degrees": s["wind_direction_degrees"],
        }
        for name, s in WIND_SCENARIOS.items()
    }


def list_locations() -> dict:
    """Return all available demo locations."""
    return {
        name: {
            "name": loc["name"],
            "latitude": loc["latitude"],
            "longitude": loc["longitude"],
            "description": loc["description"],
            "expected_platform": loc["expected_platform"],
        }
        for name, loc in DEMO_LOCATIONS.items()
    }