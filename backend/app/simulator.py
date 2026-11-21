"""Generatore di dati wearable simulati (schema ispirato a Open Wearables / Garmin)."""
from __future__ import annotations

import random
from datetime import date, timedelta
from typing import Optional

SCENARIOS = {
    "normal": "Atleta in equilibrio: carico stabile, HRV nella norma.",
    "overload": "Ultima settimana con carico quasi raddoppiato: ACWR in zona di pericolo.",
    "hrv_drop": "Carico regolare ma HRV in forte calo negli ultimi 3 giorni.",
    "recovery": "Settimana di scarico dopo un blocco intenso.",
}


def generate_series(scenario: str = "normal", days: int = 42, seed: int = 7,
                    end: Optional[date] = None) -> list[dict]:
    if scenario not in SCENARIOS:
        raise ValueError(f"Scenario sconosciuto: {scenario}")
    rnd = random.Random(seed)
    end = end or date.today()
    rows: list[dict] = []
    for i in range(days):
        d = end - timedelta(days=days - 1 - i)
        k = days - 1 - i  # 0 = oggi
        train = d.weekday() in (0, 1, 3, 4, 5)
        rpe = rnd.uniform(5.0, 6.5) if train else 0.0
        dur = float(rnd.choice([55, 60, 65])) if train else 0.0
        rmssd = rnd.gauss(62, 4)
        rhr = rnd.gauss(52, 1.2)
        sleep_eff = rnd.gauss(89, 2.5)
        sleep_h = rnd.gauss(7.6, 0.4)
        spo2 = rnd.gauss(97.5, 0.6)
        temp = rnd.gauss(33.4, 0.25)

        if scenario == "overload" and k < 7:
            if k == 3:
                rpe, dur = 0.0, 0.0
            else:
                rpe, dur = rnd.uniform(7.5, 8.5), float(rnd.choice([75, 80, 90]))
            rmssd -= (7 - k) * 1.8
            rhr += (7 - k) * 0.5
            sleep_eff -= (7 - k) * 0.8
        elif scenario == "hrv_drop" and k <= 2:
            rmssd *= 0.55
            rhr += 4.5
            sleep_eff -= 7
        elif scenario == "recovery" and k < 7:
            rpe, dur = (rnd.uniform(3.0, 4.0), 40.0) if train else (0.0, 0.0)
            rmssd += 4

        rows.append({
            "day": d.isoformat(),
            "rmssd_ms": round(max(8.0, rmssd), 1),
            "resting_hr": round(min(max(rhr, 35), 90), 1),
            "hr_max": round(rnd.gauss(171, 3)) if rpe else None,
            "sleep_hours": round(min(max(sleep_h, 4), 10), 1),
            "sleep_efficiency": round(min(max(sleep_eff, 55), 98), 1),
            "spo2": round(min(max(spo2, 94), 100), 1),
            "skin_temp_c": round(temp, 2),
            "rpe": round(rpe, 1) if rpe else None,
            "duration_min": dur or None,
            "doms": round(min(10, max(0, rnd.gauss(2.5 + (3 if scenario == "overload" and k < 5 else 0), 1))), 1),
        })
    return rows
