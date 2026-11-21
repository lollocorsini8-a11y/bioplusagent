"""Raccomandazioni deterministiche (fallback senza LLM e correzione dei guardrail)."""
from __future__ import annotations

from typing import Any, Mapping

EMERGENCY_TEXT = (
    "Se hai dolore al petto, svenimento, palpitazioni intense o fiato corto a riposo, "
    "interrompi ogni attività e chiama subito il 112. Questo sistema non sostituisce una valutazione medica."
)


def _why(r: Mapping[str, Any]) -> str:
    parts = []
    if r.get("acwr") is not None:
        parts.append(f"ACWR {r['acwr']:.2f}")
    if r.get("hrv_z") is not None:
        parts.append(f"HRV Z-score {r['hrv_z']:+.2f}")
    if r.get("resting_hr") is not None and r.get("rhr_z") is not None:
        parts.append(f"FC a riposo {r['resting_hr']:.0f} bpm (Z {r['rhr_z']:+.2f})")
    if r.get("sleep_efficiency") is not None:
        parts.append(f"efficienza sonno {r['sleep_efficiency']:.0f}%")
    return ", ".join(parts) if parts else "dati insufficienti"


def deterministic_recommendation(report: Mapping[str, Any]) -> str:
    level = report.get("level", "unknown")
    why = _why(report)
    if level == "red":
        flags = {flag.get("code") for flag in report.get("flags", [])}
        details = []
        if "ACWR_DANGER" in flags:
            details.append(
                "il carico medio degli ultimi 7 giorni è molto più alto della media delle ultime 4 settimane"
            )
        if "HRV_SUPPRESSED" in flags:
            details.append(
                "la variabilità del tempo tra i battiti è molto sotto il tuo riferimento personale"
            )
        if "RHR_ELEVATED" in flags:
            details.append("la frequenza cardiaca a riposo è sopra il tuo riferimento personale")
        if "SPO2_LOW" in flags:
            details.append("il sensore ha registrato una lettura dell'ossigeno nel sangue bassa")
        if not details:
            details.append("alcuni valori si discostano dai riferimenti di cautela del prototipo")
        summary = "Dai dati emerge che " + " e ".join(details) + "."
        if "ACWR_DANGER" in flags:
            summary += " Il rapporto sul carico è sperimentale e non predice da solo un infortunio."
        return summary + " Questi indicatori non sono una diagnosi."
    if level == "yellow":
        return (
            f"I dati richiedono cautela. Evita di aumentare il carico e valuta con il tuo professionista se modificare "
            f"la sessione. Motivo: {why}. Questa indicazione non è una prescrizione medica."
        )
    if level == "green":
        return (
            f"Non emergono segnali d'allarme nelle metriche disponibili, ma questo non certifica che allenarsi sia "
            f"sicuro né sostituisce il piano del tuo professionista. Motivo: {why}."
        )
    return (
        "Non ho dati sufficienti per formulare una raccomandazione affidabile: questo non è un via libera "
        "all'allenamento. Segui il piano concordato con il tuo professionista e sincronizza i dati di carico "
        "mancanti; l'assenza di un record non viene interpretata come riposo."
    )
