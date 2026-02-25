"""
FireBridge — Map Builder (Phase 4)
Generates an interactive Folium HTML map showing:
    - 🔴 Fire detection point with camera/confidence info
    - 🟠 Wind-skewed evacuation zone polygon
    - 💨 Wind arrow showing direction and speed
    - 📋 Dispatch log panel (county, platform, notification preview)
    - 🗺️  Satellite/street tile toggle

Author: Ian Ostrowski
"""

import folium
import json
import os
import logging
from datetime import datetime
from folium.plugins import MiniMap

log = logging.getLogger("firebridge.map_builder")

# ── Output path ────────────────────────────────────────────────────────────────
MAP_OUTPUT_PATH = "firebridge_map.html"


def build_map(detection: dict, wind: dict, zone: dict, dispatch: dict) -> str:
    """
    Build and save an interactive Folium map for the FireBridge demo.

    Args:
        detection: Pano AI detection payload
        wind: NOAA wind data
        zone: Evacuation zone from zone_builder
        dispatch: Routing + notification payload from router

    Returns:
        Path to the saved HTML map file
    """
    lat = detection["latitude"]
    lon = detection["longitude"]
    confidence_pct = int(detection["confidence"] * 100)
    wind_speed = wind["wind_speed_mph"]
    wind_cardinal = wind["wind_direction_cardinal"] or "Calm"
    wind_deg = wind["wind_direction_degrees"]
    area = zone["stats"]["area_sq_miles"]
    skew = zone["stats"]["skew_factor"]
    county = dispatch.get("county", "Unknown")
    platform = dispatch.get("platform", "Unknown")
    account = dispatch.get("account_id", "N/A")
    dispatch_status = dispatch.get("status", "unknown")

    log.info(f"Building map | Fire=({lat},{lon}) | County={county} | Platform={platform}")

    # ── Base map ───────────────────────────────────────────────────────────────
    m = folium.Map(
        location=[lat, lon],
        zoom_start=11,
        tiles="CartoDB positron",
        control_scale=True,
    )

    # Add satellite layer toggle
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri",
        name="Satellite",
        overlay=False,
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="CartoDB positron",
        name="Street Map",
        overlay=False,
        control=True,
    ).add_to(m)

    # ── Evacuation zone polygon ────────────────────────────────────────────────
    zone_geojson = zone["geojson"]

    folium.GeoJson(
        zone_geojson,
        name="Evacuation Zone",
        style_function=lambda x: {
            "fillColor": "#FF6600",
            "color": "#CC3300",
            "weight": 2.5,
            "fillOpacity": 0.30,
            "dashArray": "6, 4",
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["area_sq_miles", "skew_factor", "wind_speed_mph", "wind_direction_degrees"],
            aliases=["Area (sq mi):", "Wind Skew:", "Wind Speed (mph):", "Wind Direction (°):"],
            localize=True,
        ),
    ).add_to(m)

    # Zone boundary highlight ring
    folium.GeoJson(
        zone_geojson,
        name="Zone Boundary",
        style_function=lambda x: {
            "fillColor": "transparent",
            "color": "#FF0000",
            "weight": 1.5,
            "fillOpacity": 0,
            "dashArray": "3, 6",
        },
    ).add_to(m)

    # ── Fire detection marker ──────────────────────────────────────────────────
    fire_popup_html = f"""
    <div style="font-family: Arial, sans-serif; min-width: 220px;">
        <div style="background:#CC3300; color:white; padding:8px 12px; border-radius:4px 4px 0 0;">
            <b>🔥 WILDFIRE DETECTION</b>
        </div>
        <div style="padding:10px 12px; border:1px solid #ddd; border-top:none; border-radius:0 0 4px 4px;">
            <b>Detection ID:</b> {detection.get('detection_id', 'N/A')}<br>
            <b>Camera:</b> {detection.get('camera_id', 'N/A')}<br>
            <b>Confidence:</b> {confidence_pct}%<br>
            <b>Coordinates:</b> {lat:.4f}, {lon:.4f}<br>
            <b>Detected:</b> {detection.get('detected_at', 'N/A')[:19].replace('T', ' ')}<br>
            <hr style="margin:6px 0;">
            <i style="color:#666;">{detection.get('notes', '')}</i>
        </div>
    </div>
    """

    folium.Marker(
        location=[lat, lon],
        popup=folium.Popup(fire_popup_html, max_width=280),
        tooltip="🔥 Click — Fire Detection Point",
        icon=folium.Icon(
            color="red",
            icon="fire",
            prefix="fa",
        ),
    ).add_to(m)

    # ── Wind indicator marker ──────────────────────────────────────────────────
    wind_popup_html = f"""
    <div style="font-family: Arial, sans-serif; min-width: 200px;">
        <div style="background:#1a6496; color:white; padding:8px 12px; border-radius:4px 4px 0 0;">
            <b>💨 NOAA WIND DATA</b>
        </div>
        <div style="padding:10px 12px; border:1px solid #ddd; border-top:none; border-radius:0 0 4px 4px;">
            <b>Speed:</b> {wind_speed} mph<br>
            <b>Direction:</b> From {wind_cardinal} ({wind_deg}°)<br>
            <b>Temperature:</b> {wind.get('temperature_f', 'N/A')}°F<br>
            <b>Forecast:</b> {wind.get('short_forecast', 'N/A')}<br>
            <b>NWS Grid:</b> {wind.get('nws_grid', 'N/A')}<br>
            <b>Skew Factor:</b> {skew}x downwind<br>
            <b>Source:</b> NOAA NWS Free API
        </div>
    </div>
    """

    # Place wind marker slightly offset from fire point
    wind_lat = lat + 0.015
    wind_lon = lon + 0.015

    folium.Marker(
        location=[wind_lat, wind_lon],
        popup=folium.Popup(wind_popup_html, max_width=260),
        tooltip=f"💨 Wind: {wind_speed} mph from {wind_cardinal} — Click for details",
        icon=folium.Icon(
            color="blue",
            icon="send",
            prefix="fa",
        ),
    ).add_to(m)

    # ── Dispatch info marker ───────────────────────────────────────────────────
    notification_payload = dispatch.get("notification_payload", {})
    message = notification_payload.get("message", {})
    sms_text = message.get("sms", message.get("sms_text", "N/A"))
    email_subject = message.get("subject", message.get("email_subject", "N/A"))

    dispatch_popup_html = f"""
    <div style="font-family: Arial, sans-serif; min-width: 260px;">
        <div style="background:#2e7d32; color:white; padding:8px 12px; border-radius:4px 4px 0 0;">
            <b>📢 NOTIFICATION DISPATCHED</b>
        </div>
        <div style="padding:10px 12px; border:1px solid #ddd; border-top:none; border-radius:0 0 4px 4px;">
            <b>County:</b> {county}<br>
            <b>Platform:</b> {platform}<br>
            <b>Account:</b> {account}<br>
            <b>Status:</b> <span style="color:#2e7d32; font-weight:bold;">{dispatch_status.upper()}</span><br>
            <b>Channels:</b> SMS, Voice, Email, Push<br>
            <hr style="margin:6px 0;">
            <b>Subject:</b><br>
            <span style="font-size:11px;">{email_subject}</span><br>
            <hr style="margin:6px 0;">
            <b>SMS Preview:</b><br>
            <span style="font-size:11px; color:#333;">{sms_text}</span><br>
            <hr style="margin:6px 0;">
            <span style="color:#999; font-size:10px;">MODE: MOCK — No real notification sent</span>
        </div>
    </div>
    """

    # Place dispatch marker southwest of fire
    dispatch_lat = lat - 0.015
    dispatch_lon = lon - 0.015

    folium.Marker(
        location=[dispatch_lat, dispatch_lon],
        popup=folium.Popup(dispatch_popup_html, max_width=300),
        tooltip=f"📢 {platform} dispatch → {county} County — Click for details",
        icon=folium.Icon(
            color="green",
            icon="bullhorn",
            prefix="fa",
        ),
    ).add_to(m)

    # ── Zone center label ──────────────────────────────────────────────────────
    folium.Marker(
        location=[lat - 0.04, lon],
        icon=folium.DivIcon(
            html=f"""
            <div style="
                background: rgba(204,51,0,0.85);
                color: white;
                padding: 4px 10px;
                border-radius: 12px;
                font-size: 11px;
                font-family: Arial, sans-serif;
                font-weight: bold;
                white-space: nowrap;
                box-shadow: 0 2px 4px rgba(0,0,0,0.3);
            ">
                ⚠️ EVACUATION ZONE — {area:.1f} sq mi
            </div>
            """,
            icon_size=(220, 28),
            icon_anchor=(110, 14),
        ),
    ).add_to(m)

    # ── Info panel (top-right overlay) ────────────────────────────────────────
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    platform_color = "#CC3300" if platform == "CodeRED" else "#1a6496"

    info_panel_html = f"""
    <div style="
        position: fixed;
        top: 10px;
        right: 10px;
        z-index: 1000;
        background: white;
        border-radius: 8px;
        box-shadow: 0 2px 12px rgba(0,0,0,0.25);
        font-family: Arial, sans-serif;
        font-size: 12px;
        width: 240px;
        overflow: hidden;
    ">
        <div style="background: #1a1a2e; color: white; padding: 10px 14px;">
            <span style="font-size:15px; font-weight:bold;">🔥 FireBridge</span><br>
            <span style="font-size:10px; color:#aaa;">Pano AI → Mass Notification Middleware</span>
        </div>

        <div style="padding: 10px 14px; border-bottom: 1px solid #eee;">
            <div style="color:#CC3300; font-weight:bold; font-size:11px; margin-bottom:4px;">DETECTION</div>
            <b>{detection.get('detection_id','N/A')}</b><br>
            Confidence: <b>{confidence_pct}%</b><br>
            Camera: {detection.get('camera_id','N/A')}
        </div>

        <div style="padding: 10px 14px; border-bottom: 1px solid #eee;">
            <div style="color:#1a6496; font-weight:bold; font-size:11px; margin-bottom:4px;">WIND (NOAA)</div>
            {wind_speed} mph from {wind_cardinal}<br>
            Skew: <b>{skew}x downwind</b>
        </div>

        <div style="padding: 10px 14px; border-bottom: 1px solid #eee;">
            <div style="color:#CC6600; font-weight:bold; font-size:11px; margin-bottom:4px;">EVACUATION ZONE</div>
            Area: <b>{area:.1f} sq miles</b><br>
            Zone: Wind-skewed polygon
        </div>

        <div style="padding: 10px 14px; border-bottom: 1px solid #eee;">
            <div style="color:{platform_color}; font-weight:bold; font-size:11px; margin-bottom:4px;">DISPATCH</div>
            County: <b>{county}</b><br>
            Platform: <b style="color:{platform_color};">{platform}</b><br>
            Account: {account}<br>
            Status: <b style="color:#2e7d32;">MOCK SENT</b>
        </div>

        <div style="padding: 8px 14px; background:#f9f9f9; color:#999; font-size:10px;">
            Generated: {timestamp}<br>
            Crisis24 POC — Not for operational use
        </div>
    </div>
    """

    m.get_root().html.add_child(folium.Element(info_panel_html))

    # ── Mini map ───────────────────────────────────────────────────────────────
    MiniMap(toggle_display=True, position="bottomleft").add_to(m)

    # ── Layer control ──────────────────────────────────────────────────────────
    folium.LayerControl(position="topleft", collapsed=False).add_to(m)

    # ── Save map ───────────────────────────────────────────────────────────────
    output_path = MAP_OUTPUT_PATH
    m.save(output_path)

    log.info(f"✅ Map saved → {os.path.abspath(output_path)}")
    return os.path.abspath(output_path)


# ── Standalone test ────────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    print("\n" + "="*60)
    print("  FireBridge Map Builder — Standalone Test")
    print("="*60)

    # Use the Santa Ana wind scenario for a dramatic demo map
    # (25 mph SSE wind = 2.25x skew downwind toward NNW)
    from zone_builder import build_evacuation_zone
    from router import route_detection

    mock_detection = {
        "detection_id": "PANO-TEST-001",
        "latitude": 34.0522,
        "longitude": -118.2437,
        "confidence": 0.91,
        "camera_id": "CAM-LA-12",
        "detected_at": datetime.utcnow().isoformat(),
        "notes": "Smoke plume detected — LA County demo scenario",
    }

    # Use simulated Santa Ana wind for dramatic polygon
    mock_wind = {
        "wind_speed_mph": 25,
        "wind_direction_cardinal": "SSE",
        "wind_direction_degrees": 157.5,
        "temperature_f": 87,
        "short_forecast": "Hot and Windy",
        "forecast_time": datetime.utcnow().isoformat(),
        "nws_grid": "LOX 155,45",
        "source": "NOAA NWS Hourly Forecast API",
    }

    zone = build_evacuation_zone(
        latitude=mock_detection["latitude"],
        longitude=mock_detection["longitude"],
        wind_speed_mph=mock_wind["wind_speed_mph"],
        wind_direction_degrees=mock_wind["wind_direction_degrees"],
    )

    dispatch = route_detection(
        latitude=mock_detection["latitude"],
        longitude=mock_detection["longitude"],
        detection=mock_detection,
        wind=mock_wind,
        zone=zone,
    )

    map_path = build_map(mock_detection, mock_wind, zone, dispatch)

    print(f"\n✅ Map generated successfully!")
    print(f"   Open this file in your browser:")
    print(f"   {map_path}")
    print("\n" + "="*60 + "\n")