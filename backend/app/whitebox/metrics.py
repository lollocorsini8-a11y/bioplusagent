"""
Engine White-Box di BioPulse-Agent.

Tutte le funzioni sono pure e deterministiche: stesso input -> stesso output.
Nessuna dipendenza esterna (solo libreria standard), cosi' il modulo e'
verificabile e testabile da solo, senza LLM, database o rete.

Formule (vedi docs/ARCHITECTURE.md):
  RMSSD = sqrt( mean( (RR[i+1] - RR[i])^2 ) )
  sRPE  = RPE * durata_min                      (Foster, session-RPE)
  ACWR  = media_carico(7 giorni) / media_carico(28 giorni)
  Z     = (valore - media_baseline) / dev_std_baseline   (baseline individuale)
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from statistics import mean, stdev
from typing import Any, Mapping, Optional, Sequence

# --- Soglie (documentate in docs/ARCHITECTURE.md e ethics-review.md) --------
ACWR_LOW = 0.8
ACWR_HIGH = 1.3
ACWR_DANGER = 1.5
HRV_Z_ALERT = -1.5
HRV_Z_WATCH = -1.0
RHR_Z_ALERT = 1.5
SPO2_ALERT = 92.0
ACUTE_DAYS = 7
CHRONIC_DAYS = 28
MIN_BASELINE_POINTS = 7
SMOOTH_DAYS = 3  # media mobile per HRV e FC a riposo (riduce il rumore del singolo giorno)


# --- Primitive ---------------------------------------------------------------
def rmssd(rr_ms: Sequence[float]) -> Optional[float]:
    """Radice della media dei quadrati delle differenze tra intervalli RR successivi."""
    if rr_ms is None or len(rr_ms) < 2:
        return None
    diffs = [(b - a) ** 2 for a, b in zip(rr_ms, rr_ms[1:])]
    return math.sqrt(sum(diffs) / len(diffs))


def session_load(rpe: Optional[float], duration_min: Optional[float]) -> float:
    """Carico di sessione (Foster): RPE x minuti. Riposo = 0."""
    if not rpe or not duration_min:
        return 0.0
    return float(rpe) * float(duration_min)


def zscore(value: Optional[float], baseline: Sequence[float]) -> Optional[float]:
    """Z-score rispetto a una baseline individuale. None se la baseline e' inaffidabile."""
    if value is None:
        return None
    pts = [b for b in baseline if b is not None]
    if len(pts) < MIN_BASELINE_POINTS:
        return None
    sd = stdev(pts)
    if sd < 1e-9:
        return None
    return (value - mean(pts)) / sd


@dataclass
class AcwrResult:
    acute: Optional[float]
    chronic: Optional[float]
    ratio: Optional[float]
    zone: str  # insufficient_data | undertraining | optimal | caution | danger
    days_available: int


def acwr(daily_loads: Sequence[float], data_days: Optional[int] = None) -> AcwrResult:
    """
    ACWR su finestra di calendario. `daily_loads` e' ordinato dal piu' vecchio al piu'
    recente, con 0 nei giorni di riposo. Servono almeno 28 valori.
    """
    n = data_days if data_days is not None else len(daily_loads)
    if len(daily_loads) < CHRONIC_DAYS or n < CHRONIC_DAYS:
        return AcwrResult(None, None, None, "insufficient_data", n)
    acute = mean(daily_loads[-ACUTE_DAYS:])
    chronic = mean(daily_loads[-CHRONIC_DAYS:])
    if chronic <= 0:
        return AcwrResult(acute, chronic, None, "insufficient_data", n)
    ratio = acute / chronic
    if ratio > ACWR_DANGER:
        zone = "danger"
    elif ratio > ACWR_HIGH:
        zone = "caution"
    elif ratio >= ACWR_LOW:
        zone = "optimal"
    else:
        zone = "undertraining"
    return AcwrResult(round(acute, 1), round(chronic, 1), round(ratio, 3), zone, n)


# --- Report completo ---------------------------------------------------------
@dataclass
class Flag:
    code: str
    severity: str  # red | yellow | info
    message: str


@dataclass
class StrainReport:
    as_of: Optional[str]
    acwr: Optional[float]
    acute_load: Optional[float]
    chronic_load: Optional[float]
    acwr_zone: str
    rmssd_ms: Optional[float]
    hrv_z: Optional[float]
    resting_hr: Optional[float]
    rhr_z: Optional[float]
    sleep_efficiency: Optional[float]
    spo2: Optional[float]
    readiness: Optional[int]
    level: str  # green | yellow | red | unknown
    confidence: str  # full | partial | insufficient
    data_days: int
    flags: list = field(default_factory=list)
    explanations: list = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _num(row: Mapping[str, Any], key: str) -> Optional[float]:
    v = row.get(key)
    return None if v is None else float(v)


def compute_strain_report(rows: Sequence[Mapping[str, Any]]) -> StrainReport:
    """
    `rows`: record giornalieri con chiavi: day (date|ISO str), rmssd_ms, resting_hr,
    sleep_efficiency, spo2, load. Non serve che siano contigui o ordinati.
    """
    if not rows:
        return StrainReport(None, None, None, None, "insufficient_data", None, None, None,
                            None, None, None, None, "unknown", "insufficient", 0,
                            explanations=["Nessun dato biometrico disponibile."])

    def to_date(d: Any) -> date:
        return d if isinstance(d, date) else date.fromisoformat(str(d))

    by_day = {to_date(r["day"]): r for r in rows}
    today = max(by_day)
    window_days = [today - timedelta(days=i) for i in range(CHRONIC_DAYS - 1, -1, -1)]
    data_days = sum(
        1 for d in window_days if d in by_day and by_day[d].get("load") is not None
    )
    has_complete_load_data = data_days == CHRONIC_DAYS
    loads = [
        float(by_day[d]["load"]) if d in by_day and by_day[d].get("load") is not None else 0.0
        for d in window_days
    ]
    ac = acwr(loads, data_days)

    latest = by_day[today]
    recent_rows = [by_day[today - timedelta(days=i)] for i in range(SMOOTH_DAYS)
                   if (today - timedelta(days=i)) in by_day]
    # Baseline individuale: i 28 giorni precedenti alla finestra di smoothing.
    base_rows = [by_day[today - timedelta(days=i)] for i in range(SMOOTH_DAYS, SMOOTH_DAYS + CHRONIC_DAYS)
                 if (today - timedelta(days=i)) in by_day]

    def smooth(key: str) -> Optional[float]:
        vals = [float(r[key]) for r in recent_rows if r.get(key) is not None]
        return mean(vals) if vals else None

    rmssd_now = _num(latest, "rmssd_ms")
    rhr_now = _num(latest, "resting_hr")
    sleep_eff = _num(latest, "sleep_efficiency")
    spo2 = _num(latest, "spo2")
    rmssd_ma, rhr_ma = smooth("rmssd_ms"), smooth("resting_hr")
    hrv_z = zscore(rmssd_ma, [r["rmssd_ms"] for r in base_rows if r.get("rmssd_ms") is not None])
    rhr_z = zscore(rhr_ma, [r["resting_hr"] for r in base_rows if r.get("resting_hr") is not None])

    flags: list[Flag] = []
    expl: list[str] = []
    score = 100.0

    # ACWR
    if ac.ratio is None:
        expl.append("ACWR non calcolabile: servono carichi registrati per tutti i 28 giorni; "
                    f"giorni con record: {data_days}/28. Un giorno senza record non è considerato riposo.")
        if not has_complete_load_data:
            flags.append(Flag("ACWR_DATA_INCOMPLETE", "info",
                              "Carico non calcolabile: dati assenti o incompleti nella finestra di 28 giorni."))
    else:
        expl.append(f"ACWR = carico acuto {ac.acute} / carico cronico {ac.chronic} = {ac.ratio:.2f} "
                    f"(zona: {ac.zone}).")
        if ac.zone == "danger":
            flags.append(Flag("ACWR_DANGER", "red",
                              "Il carico medio degli ultimi 7 giorni è molto più alto della media delle ultime "
                              "4 settimane; soglia sperimentale, non è una previsione di infortunio."))
            score -= 40
        elif ac.zone == "caution":
            flags.append(Flag("ACWR_CAUTION", "yellow",
                              "Il carico recente è in salita rispetto alla media delle ultime 4 settimane; "
                              "soglia sperimentale, non è una previsione di infortunio."))
            score -= 20
        elif ac.zone == "undertraining":
            flags.append(Flag("ACWR_LOW", "info",
                              f"ACWR {ac.ratio:.2f} < {ACWR_LOW}: carico recente basso rispetto al cronico."))
            score -= 5

    # HRV
    if hrv_z is None:
        expl.append("Z-score HRV non calcolabile: baseline individuale insufficiente "
                    f"(servono {MIN_BASELINE_POINTS} misure).")
    else:
        expl.append(f"RMSSD oggi {rmssd_now:.1f} ms (media {SMOOTH_DAYS} giorni {rmssd_ma:.1f}); "
                    f"Z-score vs baseline individuale = {hrv_z:+.2f}.")
        if hrv_z < HRV_Z_ALERT:
            flags.append(Flag("HRV_SUPPRESSED", "red",
                              "La variabilità del tempo tra i battiti è molto sotto il tuo riferimento personale."))
            score -= 35
        elif hrv_z < HRV_Z_WATCH:
            flags.append(Flag("HRV_WATCH", "yellow",
                              "La variabilità del tempo tra i battiti è sotto il tuo riferimento personale."))
            score -= 20
        elif hrv_z < -0.5:
            score -= 8

    # Frequenza a riposo
    if rhr_z is not None and rhr_z > RHR_Z_ALERT:
        flags.append(Flag("RHR_ELEVATED", "yellow",
                          "La frequenza cardiaca a riposo è sopra il tuo riferimento personale."))
        score -= 15
        expl.append(f"Frequenza cardiaca a riposo elevata: Z {rhr_z:+.2f}.")

    # Sonno
    if sleep_eff is not None:
        if sleep_eff < 75:
            flags.append(Flag("SLEEP_POOR", "yellow", f"Efficienza del sonno {sleep_eff:.0f}% (bassa)."))
            score -= 10
        elif sleep_eff < 85:
            score -= 5

    # SpO2
    if spo2 is not None and spo2 < SPO2_ALERT:
        flags.append(Flag("SPO2_LOW", "red",
                          "Il sensore ha registrato una lettura dell'ossigeno nel sangue sotto la soglia di cautela."))
        score -= 25

    # Livello
    reds = [f for f in flags if f.severity == "red"]
    yellows = [f for f in flags if f.severity == "yellow"]
    score_i = int(max(0, min(100, round(score))))
    if reds:
        level = "red"
        score_i = min(score_i, 39)
    elif yellows or score_i < 70:
        level = "yellow"
    elif ac.ratio is None:
        level = "unknown"
    else:
        level = "green"

    # Confidenza
    if ac.ratio is None and hrv_z is None:
        confidence, level = "insufficient", ("red" if reds else "unknown")
    elif ac.ratio is None or hrv_z is None or data_days < 25:
        confidence = "partial"
    else:
        confidence = "full"
    if confidence != "full":
        flags.append(Flag("DATA_PARTIAL", "info", f"Dati parziali ({data_days}/28 giorni): interpretare con cautela."))

    return StrainReport(
        as_of=today.isoformat(),
        acwr=ac.ratio, acute_load=ac.acute, chronic_load=ac.chronic, acwr_zone=ac.zone,
        rmssd_ms=None if rmssd_now is None else round(rmssd_now, 1),
        hrv_z=None if hrv_z is None else round(hrv_z, 2),
        resting_hr=rhr_now, rhr_z=None if rhr_z is None else round(rhr_z, 2),
        sleep_efficiency=sleep_eff, spo2=spo2,
        readiness=None if level == "unknown" else score_i,
        level=level, confidence=confidence, data_days=data_days,
        flags=[asdict(f) for f in flags], explanations=expl,
    )
