"""Fonte wearable sintetica con cursore incrementale per il prototipo."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

from .simulator import generate_series

PROVIDER_ID = "synthetic_wearable"
OVERLAP_DAYS = 1


def fetch_synthetic_records(
    scenario: str = "normal",
    seed: int = 7,
    cursor_day: Optional[date] = None,
) -> list[dict]:
    """Simula il payload di un provider remoto e rilegge l'ultimo giorno per correzioni."""
    records = generate_series(scenario=scenario, seed=seed)
    if cursor_day is not None:
        first_day = cursor_day - timedelta(days=OVERLAP_DAYS)
        records = [record for record in records if date.fromisoformat(record["day"]) >= first_day]
    return [
        {
            "date": record["day"],
            "hrv_rmssd_ms": record["rmssd_ms"],
            "resting_heart_rate_bpm": record["resting_hr"],
            "max_heart_rate_bpm": record["hr_max"],
            "sleep_duration_hours": record["sleep_hours"],
            "sleep_efficiency_percent": record["sleep_efficiency"],
            "oxygen_saturation_percent": record["spo2"],
            "skin_temperature_celsius": record["skin_temp_c"],
            "session_rpe": record["rpe"],
            "session_duration_minutes": record["duration_min"],
            "muscle_soreness": record["doms"],
        }
        for record in records
    ]


def normalize_synthetic_record(record: dict) -> dict:
    return {
        "day": record.get("date"),
        "rmssd_ms": record.get("hrv_rmssd_ms"),
        "resting_hr": record.get("resting_heart_rate_bpm"),
        "hr_max": record.get("max_heart_rate_bpm"),
        "sleep_hours": record.get("sleep_duration_hours"),
        "sleep_efficiency": record.get("sleep_efficiency_percent"),
        "spo2": record.get("oxygen_saturation_percent"),
        "skin_temp_c": record.get("skin_temperature_celsius"),
        "rpe": record.get("session_rpe"),
        "duration_min": record.get("session_duration_minutes"),
        "doms": record.get("muscle_soreness"),
    }
