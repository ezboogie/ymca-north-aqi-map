#!/usr/bin/env python3
"""Fetch PurpleAir readings and match each YMCA to its nearest recent sensor."""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
LOCATIONS_PATH = ROOT / "locations.json"
OUTPUT_PATH = ROOT / "aqi-data.json"
API_URL = "https://api.purpleair.com/v1/sensors"
MAX_SENSOR_DISTANCE_KM = 80.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * radius_km * math.asin(math.sqrt(a))


def epa_correct_pm25(raw_pm25: float, humidity: float) -> float:
    """Apply the EPA correction used for PurpleAir PM2.5 observations."""
    if raw_pm25 < 30:
        corrected = 0.524 * raw_pm25 - 0.0862 * humidity + 5.75
    elif raw_pm25 < 50:
        corrected = (
            0.786 * raw_pm25
            - 0.0862 * humidity
            + 5.75
            - 0.0252 * (raw_pm25 - 30) ** 2
        )
    else:
        corrected = 0.786 * raw_pm25 - 0.0862 * humidity + 5.75
    return max(0.0, corrected)


AQI_BREAKPOINTS = (
    (0.0, 9.0, 0, 50),
    (9.1, 35.4, 51, 100),
    (35.5, 55.4, 101, 150),
    (55.5, 125.4, 151, 200),
    (125.5, 225.4, 201, 300),
    (225.5, 325.4, 301, 500),
    (325.5, 99999.9, 501, 999),
)


def aqi_from_pm25(pm25: float) -> int:
    concentration = math.floor(max(0.0, pm25) * 10) / 10
    for low_pm, high_pm, low_aqi, high_aqi in AQI_BREAKPOINTS:
        if low_pm <= concentration <= high_pm:
            value = ((high_aqi - low_aqi) / (high_pm - low_pm)) * (concentration - low_pm) + low_aqi
            return min(999, round(value))
    return 999


def category_for_aqi(aqi: int) -> str:
    if aqi <= 50:
        return "Good"
    if aqi <= 100:
        return "Moderate"
    if aqi <= 150:
        return "Unhealthy for Sensitive Groups"
    if aqi <= 200:
        return "Unhealthy"
    if aqi <= 300:
        return "Very Unhealthy"
    return "Hazardous"


def fetch_sensors(api_key: str) -> list[dict]:
    fields = [
        "sensor_index",
        "name",
        "latitude",
        "longitude",
        "pm2.5_10minute",
        "humidity",
        "confidence",
        "last_seen",
    ]
    params = {
        "fields": ",".join(fields),
        "nwlat": 49.1,
        "nwlng": -95.0,
        "selat": 44.0,
        "selng": -90.0,
        "location_type": 0,
        "max_age": 3600,
    }
    request = Request(
        f"{API_URL}?{urlencode(params)}",
        headers={"X-API-Key": api_key, "User-Agent": "ymca-north-aqi-map/1.0"},
    )
    with urlopen(request, timeout=45) as response:
        payload = json.load(response)

    returned_fields = payload.get("fields", [])
    rows = payload.get("data", [])
    sensors = []
    for row in rows:
        sensor = dict(zip(returned_fields, row))
        required = ("sensor_index", "latitude", "longitude", "pm2.5_10minute", "humidity")
        if any(sensor.get(field) is None for field in required):
            continue
        confidence = sensor.get("confidence")
        if confidence is not None and float(confidence) < 50:
            continue
        sensors.append(sensor)
    return sensors


def build_location_readings(locations: list[dict], sensors: list[dict]) -> list[dict]:
    readings = []
    for location in locations:
        nearest = None
        nearest_distance = float("inf")
        for sensor in sensors:
            distance = haversine_km(
                location["lat"],
                location["lng"],
                float(sensor["latitude"]),
                float(sensor["longitude"]),
            )
            if distance < nearest_distance:
                nearest, nearest_distance = sensor, distance

        if nearest is None or nearest_distance > MAX_SENSOR_DISTANCE_KM:
            readings.append({"id": location["id"], "status": "unavailable"})
            continue

        raw_pm25 = float(nearest["pm2.5_10minute"])
        humidity = float(nearest["humidity"])
        corrected_pm25 = epa_correct_pm25(raw_pm25, humidity)
        aqi = aqi_from_pm25(corrected_pm25)
        last_seen = nearest.get("last_seen")
        sensor_time = None
        if last_seen is not None:
            sensor_time = datetime.fromtimestamp(int(last_seen), timezone.utc).isoformat()

        readings.append(
            {
                "id": location["id"],
                "status": "ok",
                "aqi": aqi,
                "category": category_for_aqi(aqi),
                "pm25_corrected": round(corrected_pm25, 1),
                "pm25_raw": round(raw_pm25, 1),
                "humidity": round(humidity, 1),
                "sensor_index": int(nearest["sensor_index"]),
                "sensor_name": nearest.get("name") or f"Sensor {nearest['sensor_index']}",
                "sensor_distance_km": round(nearest_distance, 1),
                "sensor_last_seen": sensor_time,
            }
        )
    return readings


def write_output(payload: dict) -> None:
    OUTPUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    locations = json.loads(LOCATIONS_PATH.read_text(encoding="utf-8"))
    api_key = os.environ.get("PURPLEAIR_API_KEY", "").strip()
    if not api_key:
        write_output(
            {
                "status": "configuration_required",
                "generated_at": None,
                "source": "PurpleAir",
                "message": "Add the PURPLEAIR_API_KEY repository secret, then run the deployment workflow.",
                "locations": [],
            }
        )
        print("PURPLEAIR_API_KEY is not configured; wrote placeholder data.")
        return

    sensors = fetch_sensors(api_key)
    if not sensors:
        raise RuntimeError("PurpleAir returned no usable outdoor sensor readings for the configured region.")

    generated_at = datetime.now(timezone.utc).isoformat()
    readings = build_location_readings(locations, sensors)
    write_output(
        {
            "status": "ok",
            "generated_at": generated_at,
            "source": "PurpleAir",
            "reading_window": "10-minute PM2.5",
            "sensor_count": len(sensors),
            "locations": readings,
        }
    )
    print(f"Matched {len(readings)} YMCA locations using {len(sensors)} PurpleAir sensors.")


if __name__ == "__main__":
    main()
