"""Sanificazione dei dati telemetrici e del testo utente (test T1, T2)."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from .metrics import rmssd, session_load

HR_MIN, HR_MAX = 20, 250          # fuori scala fisiologica: sensore difettoso
RR_MIN, RR_MAX = 250, 2500        # ms (24-240 bpm)
DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y")
MAX_TEXT_LEN = 2000


def parse_day(value: Any) -> Optional[date]:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(value.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _num(rec: dict, key: str, lo: float, hi: float, errors: list[str], label: str) -> Optional[float]:
    v = rec.get(key)
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        errors.append(f"{label}: valore non numerico ({v!r}).")
        return None
    if not (lo <= f <= hi):
        errors.append(f"{label}: {f:g} fuori scala ({lo:g}-{hi:g}). Ricalibra o ricollega il sensore.")
        return None
    return f


@dataclass
class CleanRecord:
    day: date
    rmssd_ms: Optional[float]
    resting_hr: Optional[float]
    hr_max: Optional[float]
    sleep_hours: Optional[float]
    sleep_efficiency: Optional[float]
    spo2: Optional[float]
    skin_temp_c: Optional[float]
    rpe: Optional[float]
    duration_min: Optional[float]
    doms: Optional[float]
    load: float


@dataclass
class SanitizeResult:
    clean: Optional[CleanRecord] = None
    errors: list[str] = field(default_factory=list)


def sanitize_record(rec: Any) -> SanitizeResult:
    if not isinstance(rec, dict) or not rec:
        return SanitizeResult(errors=["Record vuoto o non valido."])
    errors: list[str] = []
    day = parse_day(rec.get("day"))
    if day is None:
        errors.append(f"Data non riconosciuta ({rec.get('day')!r}). Usa il formato AAAA-MM-GG.")
    elif day > date.today():
        errors.append("Data nel futuro non ammessa.")

    resting = _num(rec, "resting_hr", HR_MIN, HR_MAX, errors, "Frequenza a riposo")
    hrmax = _num(rec, "hr_max", HR_MIN, HR_MAX, errors, "Frequenza massima")
    rmssd_v = _num(rec, "rmssd_ms", 1, 400, errors, "RMSSD")
    rr = rec.get("rr_intervals_ms")
    if rr is not None:
        if (not isinstance(rr, list) or len(rr) < 2
                or any(not isinstance(x, (int, float)) or not (RR_MIN <= x <= RR_MAX) for x in rr)):
            errors.append("Intervalli RR non validi (fuori 250-2500 ms o troppo pochi). Ricalibra il sensore.")
        else:
            rmssd_v = rmssd(rr)
    sleep_h = _num(rec, "sleep_hours", 0, 18, errors, "Ore di sonno")
    sleep_e = _num(rec, "sleep_efficiency", 0, 100, errors, "Efficienza sonno")
    spo2 = _num(rec, "spo2", 70, 100, errors, "SpO2")
    temp = _num(rec, "skin_temp_c", 25, 42, errors, "Temperatura cutanea")
    rpe = _num(rec, "rpe", 0, 10, errors, "RPE")
    dur = _num(rec, "duration_min", 0, 600, errors, "Durata sessione")
    doms = _num(rec, "doms", 0, 10, errors, "DOMS")

    if errors or day is None:
        return SanitizeResult(errors=errors)
    return SanitizeResult(clean=CleanRecord(day, rmssd_v, resting, hrmax, sleep_h, sleep_e, spo2, temp,
                                            rpe, dur, doms, session_load(rpe, dur)))


def sanitize_batch(records: Any) -> tuple[list[CleanRecord], list[dict]]:
    """Ritorna (record validi, record scartati con motivo). Mai eccezioni."""
    if not isinstance(records, list) or not records:
        return [], [{"index": None, "day": None, "errors": ["Payload vuoto: nessun dato da elaborare."]}]
    ok, bad = [], []
    for i, rec in enumerate(records):
        res = sanitize_record(rec)
        if res.clean:
            ok.append(res.clean)
        else:
            bad.append({"index": i, "day": rec.get("day") if isinstance(rec, dict) else None,
                        "errors": res.errors})
    return ok, bad


def clean_user_text(text: Any) -> tuple[str, Optional[str]]:
    """Ritorna (testo ripulito, messaggio d'errore | None)."""
    if text is None or not isinstance(text, str) or not text.strip():
        return "", "Il messaggio è vuoto. Scrivi come ti senti, l'RPE dell'ultima sessione o una domanda."
    t = " ".join(text.split())
    if len(t) > MAX_TEXT_LEN:
        t = t[:MAX_TEXT_LEN]
    return t, None
