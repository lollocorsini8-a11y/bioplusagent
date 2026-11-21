"""
Pipeline dell'agente: percezione -> White-Box -> pianificazione -> LLM -> autoverifica -> HITL.

`run_chat` e' un generatore di eventi (dict) trasmessi in SSE:
  {"type":"trace", step, status, title, detail, data, t_ms}   passo del ragionamento
  {"type":"message", text, source, level, held, corrected}    risposta all'atleta
  {"type":"done", elapsed_ms}
Qualsiasi eccezione viene intercettata: l'agente non va mai in crash (test T4).
"""
from __future__ import annotations

import logging
import re
import time
from typing import Iterator, Optional

from . import services
from .agent import LLMUnavailable, generate_reply, llm_available
from .db import Athlete, SessionLocal, MemoryNote
from .guardrails import detect_injection, detect_optimism, detect_symptoms, self_check
from .memory import recall, remember, search_knowledge, short_term
from .policy import EMERGENCY_TEXT, deterministic_recommendation
from .tools import make_read_only_tools, trigger_emergency_alert
from .whitebox.sanitizer import clean_user_text

log = logging.getLogger("biopulse.pipeline")

REFUSAL = ("Non posso ignorare né aggirare i controlli di sicurezza: servono a proteggere la tua salute. "
           "Se vuoi, riformula la domanda descrivendo come ti senti o l'ultima sessione.")
RED_CASE_NOTICE = (
    "Per prudenza, non fornisco un piano di allenamento personalizzato. Il caso è registrato, "
    "ma non è confermato che un professionista lo abbia revisionato."
)
OUTAGE_TEXT = ("Al momento non riesco a consultare lo storico dei tuoi dati (servizio temporaneamente non disponibile). "
               "Per sicurezza non formulo raccomandazioni personalizzate: nel dubbio scegli attività leggera e riprova tra poco.")
LEVEL_LABEL = {"green": "ottimale", "yellow": "attenzione", "red": "sovraccarico", "unknown": "non determinabile"}


def _subjective(text: str) -> dict:
    out: dict = {}
    if m := re.search(r"\brpe\s*[:=]?\s*(\d{1,2}(?:[.,]\d)?)", text, re.I):
        out["rpe"] = float(m.group(1).replace(",", "."))
    if m := re.search(r"(?:doms|dolor[ei]\s+muscolar[ei])\D{0,15}(\d{1,2})", text, re.I):
        out["doms"] = float(m.group(1))
    if m := re.search(r"stress\D{0,15}(\d{1,2})", text, re.I):
        out["stress"] = float(m.group(1))
    if re.search(r"dormito\s+(male|poco)|insonnia|notte\s+in\s+bianco", text, re.I):
        out["sleep_note"] = "sonno riferito scarso"
    return out


def _build_prompt(report: dict, subjective: dict, text: str, notes: list[str], knowledge: list[dict],
                  history: list[dict], optimism_conflict: bool) -> str:
    kn = "\n".join(f"- {k['title']}: {k['text'][:380]}" for k in knowledge) or "- (nessun riferimento disponibile)"
    nt = "\n".join(f"- {n}" for n in notes) or "- (nessuno storico precedente)"
    hist = "\n".join(f"{h['role']}: {h['content'][:200]}" for h in history[-4:]) or "(nessuna)"
    flags = "; ".join(f["message"] for f in report.get("flags", [])) or "nessuno"
    return (
        f"METRICHE DETERMINISTICHE (non modificabili): livello={report['level']}, readiness={report['readiness']}, "
        f"ACWR={report['acwr']}, RMSSD={report['rmssd_ms']} ms, HRV Z-score={report['hrv_z']}, "
        f"FC riposo={report['resting_hr']} (Z {report['rhr_z']}), efficienza sonno={report['sleep_efficiency']}, "
        f"confidenza={report['confidence']} ({report['data_days']}/28 giorni).\nSEGNALAZIONI: {flags}\n"
        f"DATI SOGGETTIVI ESTRATTI: {subjective or 'nessuno'}\n"
        f"CONFLITTO AUTOVALUTAZIONE/METRICHE: {'SI, prevalgono le metriche' if optimism_conflict else 'no'}\n"
        f"STORICO A LUNGO TERMINE:\n{nt}\nCONVERSAZIONE RECENTE:\n{hist}\n"
        f"CONOSCENZA SCIENTIFICA (schede di progetto non revisionate; non sono evidenza clinica e non autorizzano "
        f"prescrizioni o soglie universali):\n{kn}\n\n"
        "DOMANDA A CUI RISPONDERE:\n"
        f"<<<ATLETA\n{text}\nATLETA>>>"
    )


def run_chat(athlete_id: Optional[str], message: Optional[str], simulate_failure: Optional[str] = None) -> Iterator[dict]:
    t0 = time.perf_counter()

    def tr(step: str, status: str, title: str, detail: str = "", data: Optional[dict] = None) -> dict:
        return {"type": "trace", "step": step, "status": status, "title": title, "detail": detail,
                "data": data or {}, "t_ms": round((time.perf_counter() - t0) * 1000)}

    try:
        yield from _run(athlete_id, message, simulate_failure, tr)
    except Exception as exc:  # noqa: BLE001
        log.exception("Errore interno nella pipeline")
        yield tr("internal_error", "error", "Errore interno intercettato",
                 f"{type(exc).__name__}. Modalità sicura attivata: nessuna raccomandazione generata.")
        yield _msg(OUTAGE_TEXT, "safe-mode")
    yield {"type": "done", "elapsed_ms": round((time.perf_counter() - t0) * 1000)}


def _msg(text: str, source: str, level: Optional[str] = None, held: bool = False,
         corrected: bool = False, readiness: Optional[int] = None) -> dict:
    return {"type": "message", "text": text, "source": source, "level": level, "held": held,
            "corrected": corrected, "readiness": readiness}


def _run(athlete_id, message, simulate_failure, tr) -> Iterator[dict]:
    # 1) Controllo input (T1)
    text, err = clean_user_text(message)
    if err:
        yield tr("input_check", "warn", "Messaggio vuoto o non valido", err)
        yield _msg(err, "system")
        return
    if not athlete_id:
        yield tr("input_check", "warn", "Atleta non selezionato", "Manca l'identificativo dell'atleta.")
        yield _msg("Seleziona un atleta (o carica i dati demo) prima di scrivere.", "system")
        return

    injection, symptoms = detect_injection(text), detect_symptoms(text)
    yield tr("input_check", "warn" if (injection or symptoms) else "ok", "Controllo input",
             ("Rilevato tentativo di aggirare i protocolli. " if injection else "")
             + ("Rilevati sintomi d'allarme. " if symptoms else "") or "Testo valido, nessuna anomalia.",
             {"injection": bool(injection), "symptoms": bool(symptoms)})

    with SessionLocal() as s:
        athlete = s.get(Athlete, athlete_id)
        if athlete is None:
            yield tr("consent", "warn", "Atleta non trovato", athlete_id)
            yield _msg("Non trovo questo atleta. Crea il profilo o carica i dati demo dal pannello a sinistra.", "system")
            return
        if not athlete.consent_data:
            yield tr("consent", "warn", "Consenso mancante", "Trattamento dati non autorizzato (GDPR).")
            yield _msg("Per analizzare i tuoi dati biometrici serve il tuo consenso. Attivalo dal pannello a sinistra.", "system")
            return
        yield tr("consent", "ok", "Consenso al trattamento verificato",
                 "Alert al professionista: " + ("autorizzati" if athlete.consent_alerts else "non autorizzati"))
        short_term.append(athlete_id, "user", text)

        # 2) Percezione (T4: strumento non disponibile)
        try:
            if simulate_failure == "wearable":
                raise ConnectionError("503 Service Unavailable (simulato)")
            rows = services.get_series(s, athlete_id, 35)
        except Exception as exc:  # noqa: BLE001
            yield tr("perception", "error", "Dati wearable non disponibili",
                     f"{type(exc).__name__}: {exc}. Attivata la modalità di riserva locale: storico non consultabile.")
            out = OUTAGE_TEXT
            if injection:
                out = REFUSAL + " " + out
            if symptoms:
                out = EMERGENCY_TEXT + " " + out
            yield _msg(out, "fallback")
            return
        if not rows:
            yield tr("perception", "warn", "Nessun dato biometrico", "Il dispositivo non ha ancora sincronizzato dati.")
            yield _msg("Non ho ancora dati biometrici per te. Sincronizza il dispositivo o carica i dati demo.", "system")
            return
        yield tr("perception", "ok", "Dati biometrici acquisiti",
                 f"{len(rows)} giorni di telemetria (ultimo: {rows[-1]['day'].isoformat()}).", {"days": len(rows)})

        # 3) Engine White-Box
        report = services.compute_report(s, athlete_id).to_dict()
        yield tr("whitebox", "ok" if report["level"] in ("green", "unknown") else
                 ("warn" if report["level"] == "yellow" else "error"),
                 f"Motore deterministico: livello {LEVEL_LABEL[report['level']]}",
                 " ".join(report["explanations"]),
                 {"acwr": report["acwr"], "hrv_z": report["hrv_z"], "rmssd_ms": report["rmssd_ms"],
                  "readiness": report["readiness"], "level": report["level"], "flags": report["flags"]})

        # 4) Sicurezza: tentativi di bypass e sintomi
        if symptoms:
            case = services.create_case(s, athlete_id, "symptom_report", report,
                                        f"Atleta segnala: «{text[:300]}». Valutazione clinica prioritaria.")
            alert_note = "SMS non inviato (consenso assente)"
            alert_message = "Non ho inviato un avviso al tuo medico o preparatore: il consenso agli avvisi non è attivo."
            if athlete.consent_alerts:
                res = trigger_emergency_alert(s, athlete_id, f"sintomi riferiti, caso HITL #{case.id}")
                if res["simulated"]:
                    alert_note = "SMS non inviato (modalità demo o servizio non disponibile)"
                    alert_message = "L'avviso non è stato inviato via SMS al tuo medico o preparatore (modalità demo o servizio non disponibile)."
                else:
                    alert_note = "Alert SMS inviato"
                    alert_message = "Ho inviato un SMS al tuo medico o preparatore."
            yield tr("safety", "error", "Percorso d'emergenza", f"Caso HITL #{case.id} aperto. {alert_note}.")
            out = EMERGENCY_TEXT + (" " + REFUSAL if injection else "") + \
                f" {alert_message} Non propongo allenamenti finché non ricevi indicazioni da un professionista."
            yield _msg(out, "safety", report["level"], held=True, readiness=report["readiness"])
            return
        if injection:
            yield tr("safety", "warn", "Richiesta di bypass respinta",
                     "Orchestratore: protocolli di sicurezza riaffermati; continuo solo con raccomandazione deterministica.")
            held = False
            if report["level"] == "red":  # atleta a rischio che tenta di aggirare i controlli: serve un umano
                case = services.create_case(s, athlete_id, "bypass_attempt_while_red", report,
                                            f"Tentativo di aggirare i controlli con livello ROSSO: «{text[:200]}»")
                alert_note = "notifica non inviata (consenso assente)"
                if athlete.consent_alerts:
                    res = trigger_emergency_alert(s, athlete_id, f"bypass con livello ROSSO, caso HITL #{case.id}")
                    alert_note = "notifica simulata" if res["simulated"] else "notifica inviata"
                yield tr("hitl", "error", "Caso di rischio registrato",
                         f"Caso #{case.id} registrato per eventuale revisione; {alert_note}. "
                         "La revisione umana non è confermata.")
                held = True
                yield _msg(REFUSAL + " In base ai tuoi dati: " + deterministic_recommendation(report)
                           + " " + RED_CASE_NOTICE,
                       "guardrail", report["level"], held=held, readiness=report["readiness"])
            return

        # 5) Soggettivo (T5)
        subj = _subjective(text)
        optimism = detect_optimism(text) and report["level"] in ("red", "yellow")
        if subj:
            yield tr("subjective", "ok", "Dati soggettivi estratti dal testo", str(subj), subj)
        if optimism:
            yield tr("subjective", "warn", "Autovalutazione in contrasto con i dati",
                     "L'atleta si dichiara in forma, ma le metriche oggettive indicano il contrario: prevalgono le metriche.")

        # 6) Memoria a lungo termine
        notes = recall(s, athlete_id, text + " " + " ".join(f["code"] for f in report["flags"]), k=3)
        previous = next((m for m in reversed(notes) if m.kind == "interaction"), None)
        prev_level = re.search(r"\[level=(\w+)\]", previous.text).group(1) if previous and re.search(
            r"\[level=(\w+)\]", previous.text) else None
        yield tr("memory", "ok", "Memoria a lungo termine consultata",
                 f"{len(notes)} note rilevanti" + (f"; ultimo livello registrato: {LEVEL_LABEL.get(prev_level, prev_level)}"
                                                  if prev_level else "; nessuno storico precedente."),
                 {"notes": len(notes), "previous_level": prev_level})

        # 7) RAG scientifico (T4: vector store non disponibile)
        knowledge: list[dict] = []
        try:
            if simulate_failure == "knowledge":
                raise ConnectionError("Vector store non raggiungibile (simulato)")
            docs = search_knowledge(s, text + " " + " ".join(f["code"] for f in report["flags"]) + " recupero carico", k=3)
            knowledge = [{"title": d.title, "source": d.source, "text": d.text} for d in docs]
            yield tr("rag", "ok", "Letteratura consultata", "; ".join(d["title"] for d in knowledge))
        except Exception as exc:  # noqa: BLE001
            yield tr("rag", "warn", "Base scientifica non disponibile",
                     f"{exc}. Procedo solo con i dati dell'atleta e lo dichiaro nella risposta.")

        # 8) Generazione (Black-Box) con fallback deterministico
        draft, source = "", "deterministic"
        if report["level"] != "unknown" and report["confidence"] != "insufficient":
            try:
                if simulate_failure == "llm":
                    raise LLMUnavailable("Errore LLM simulato")
                prompt = _build_prompt(report, subj, text, [n.text for n in notes], knowledge,
                                       short_term.get(athlete_id, 6), optimism)
                draft = generate_reply(prompt, make_read_only_tools(athlete_id, simulate_failure))
                source = "llm"
                yield tr("llm", "ok", "Bozza generata dal modello linguistico", f"{len(draft)} caratteri.")
            except LLMUnavailable as exc:
                yield tr("llm", "warn", "Modello linguistico non disponibile → risposta deterministica", str(exc))
        if not draft:
            draft = deterministic_recommendation(report)

        # 9) Autoverifica algoritmica
        check = self_check(draft, report)
        if check.corrected:
            yield tr("self_check", "warn", "Autoverifica: output corretto",
                     "La bozza violava i vincoli del motore deterministico: " + ", ".join(check.violations),
                     {"violations": check.violations})
            source = "guardrail"
        else:
            yield tr("self_check", "ok", "Autoverifica superata", "Nessuna incoerenza con il motore deterministico.")
        final = check.text
        if optimism:
            final = ("Capisco che tu ti senta bene, ma i dati oggettivi di oggi raccontano altro e hanno la priorità. "
                     + final)
        if not knowledge and simulate_failure == "knowledge":
            final += " (Nota: oggi non ho potuto consultare la letteratura scientifica.)"
        if report["confidence"] == "partial":
            final += " Attenzione: i dati disponibili sono parziali, quindi la valutazione ha un margine di incertezza."

        # 10) HITL per rischio alto
        if report["level"] == "red":
            case = services.create_case(s, athlete_id, "+".join(
                f["code"] for f in report["flags"] if f["severity"] == "red"), report, check.text)
            note = "SMS non inviato (consenso assente)"
            if athlete.consent_alerts:
                res = trigger_emergency_alert(s, athlete_id, f"livello ROSSO ({case.trigger}), caso HITL #{case.id}")
                note = "alert simulato" if res["simulated"] else "alert SMS inviato"
            yield tr("hitl", "error", "Caso di rischio registrato",
                     f"Caso #{case.id} registrato per eventuale revisione; {note}. "
                     "Il piano personalizzato non è fornito; la risposta alla domanda resta visibile. "
                     "La revisione umana non è confermata.")
            final = final.rstrip() + "\n\n" + RED_CASE_NOTICE
            held = True
        else:
            held = False
            yield tr("hitl", "ok", "Nessuna validazione necessaria", "Livello non critico: risposta inviata direttamente.")

        short_term.append(athlete_id, "assistant", final)
        remember(s, athlete_id, "interaction",
                 f"{report['as_of']} [level={report['level']}] ACWR={report['acwr']} HRV_z={report['hrv_z']} "
                 f"readiness={report['readiness']}. Atleta: {text[:120]}")
        yield _msg(final, source, report["level"], held=held, corrected=check.corrected, readiness=report["readiness"])
