"""Test del motore White-Box (solo libreria standard: girano ovunque)."""
import math

from app.simulator import generate_series
from app.whitebox.metrics import ACWR_DANGER, acwr, compute_strain_report, rmssd, session_load, zscore
from app.whitebox.sanitizer import sanitize_batch


def _report(scenario, seed=3):
    ok, bad = sanitize_batch(generate_series(scenario, seed=seed))
    assert not bad
    return compute_strain_report([c.__dict__ for c in ok])


def test_rmssd_valore_noto():
    assert math.isclose(rmssd([800, 810, 790, 805]), math.sqrt((100 + 400 + 225) / 3))
    assert rmssd([800]) is None


def test_session_load():
    assert session_load(6, 60) == 360
    assert session_load(None, 60) == 0 and session_load(5, 0) == 0


def test_acwr_zone():
    base = [100.0] * 28
    assert acwr(base).zone == "optimal" and acwr(base).ratio == 1.0
    assert acwr([100.0] * 21 + [140.0] * 7).zone == "optimal"          # 140 / 110 = 1.27
    assert acwr([100.0] * 21 + [150.0] * 7).zone == "caution"          # 150 / 112.5 = 1.33
    assert acwr([100.0] * 21 + [200.0] * 7).zone == "danger"           # 200 / 125 = 1.6
    assert acwr([100.0] * 21 + [20.0] * 7).zone == "undertraining"
    assert acwr([100.0] * 10).zone == "insufficient_data"


def test_zscore_baseline_individuale():
    base = [60, 62, 61, 63, 59, 60, 62, 61]
    assert zscore(40, base) < -1.5
    assert zscore(61, base) is not None and abs(zscore(61, base)) < 1
    assert zscore(40, [60, 61]) is None            # baseline troppo corta
    assert zscore(40, [60] * 10) is None           # varianza nulla


def test_normale_non_e_rosso():
    for seed in range(1, 40):
        assert _report("normal", seed).level in ("green", "yellow")


def test_overload_e_rosso_con_acwr_oltre_soglia():
    for seed in range(1, 40):
        r = _report("overload", seed)
        assert r.level == "red" and r.acwr > ACWR_DANGER and r.readiness <= 39
        assert "ACWR_DANGER" in [f["code"] for f in r.flags]
        messages = " ".join(flag["message"] for flag in r.flags)
        assert "zona di pericolo per infortuni" not in messages
        assert "non è una previsione di infortunio" in messages
        assert "soppressione parasimpatica" not in messages


def test_calo_hrv_e_rosso():
    for seed in range(1, 40):
        r = _report("hrv_drop", seed)
        assert r.level == "red" and r.hrv_z < -1.5


def test_recovery_non_e_rosso():
    for seed in range(1, 20):
        assert _report("recovery", seed).level != "red"


def test_dati_insufficienti_non_inventano_nulla():
    ok, _ = sanitize_batch(generate_series("overload", days=6))
    r = compute_strain_report([c.__dict__ for c in ok])
    assert r.acwr is None and r.confidence == "insufficient"
    assert compute_strain_report([]).level == "unknown"


def test_giorni_senza_record_non_sono_riposo():
    ok, _ = sanitize_batch(generate_series("normal", days=42))
    rows = [c.__dict__ for c in ok]
    missing_day = rows[-10]["day"]
    incomplete = [row for row in rows if row["day"] != missing_day]

    report = compute_strain_report(incomplete)

    assert report.acwr is None
    assert report.level == "unknown"
    assert report.readiness is None
    assert report.confidence == "partial"
    assert "ACWR_DATA_INCOMPLETE" in [flag["code"] for flag in report.flags]
    assert any("non è considerato riposo" in text for text in report.explanations)


def test_determinismo():
    assert _report("overload", 5).to_dict() == _report("overload", 5).to_dict()
