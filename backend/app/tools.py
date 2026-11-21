"""
Tool dell'agente (decoratore @tool di Agno quando disponibile).

Sicurezza: all'LLM sono esposti SOLO tool di lettura. `trigger_emergency_alert`
è definito qui ma viene invocato esclusivamente dalla pipeline deterministica:
l'agente non può mandare SMS da solo (Human-in-the-Loop).
"""
from __future__ import annotations

import json
from typing import Callable, Optional

from . import services
from .alerts import send_alert
from .db import SessionLocal
from .memory import search_knowledge


def _as_tool(fn: Callable) -> Callable:
    try:
        from agno.tools import tool
        return tool(fn)
    except Exception:  # Agno assente o API diversa: Agno accetta comunque funzioni Python semplici
        return fn


def make_read_only_tools(athlete_id: str, simulate_failure: Optional[str] = None) -> list[Callable]:
    def fetch_biometric_series(days: int = 28) -> str:
        """Estrae dal database le metriche fisiologiche giornaliere dell'atleta (HRV, FC a riposo, sonno, carico). `days` massimo 28."""
        if simulate_failure == "wearable":
            raise ConnectionError("503 Service Unavailable (simulato)")
        with SessionLocal() as s:
            rows = services.get_series(s, athlete_id, min(max(int(days), 1), 28))
        return json.dumps([{**r, "day": r["day"].isoformat()} for r in rows], ensure_ascii=False)

    def compute_strain_metrics() -> str:
        """Calcola con il motore deterministico ACWR, Z-score HRV, Z-score FC a riposo, readiness e livello di rischio."""
        with SessionLocal() as s:
            return json.dumps(services.compute_report(s, athlete_id).to_dict(), ensure_ascii=False)

    def search_longevity_knowledge(query: str) -> str:
        """Cerca nella base scientifica indicazioni su recupero, carico, HRV, sonno e longevità. Ritorna i passaggi più pertinenti."""
        if simulate_failure == "knowledge":
            raise ConnectionError("Vector store non raggiungibile (simulato)")
        with SessionLocal() as s:
            docs = search_knowledge(s, query, k=3)
            return json.dumps([{"title": d.title, "source": d.source, "text": d.text} for d in docs],
                              ensure_ascii=False)

    return [_as_tool(fetch_biometric_series), _as_tool(compute_strain_metrics),
            _as_tool(search_longevity_knowledge)]


def trigger_emergency_alert(session, athlete_id: str, reason: str) -> dict:
    """Notifica il professionista (Twilio o simulazione). Chiamata solo dalla pipeline, mai dall'LLM."""
    return send_alert(session, athlete_id, f"[BioPulse] Atleta {athlete_id}: {reason}")
