"use client";

import { Pulsi } from "@/components/mascot/Pulsi";
import type { PulsiState } from "@/components/mascot/pulsi-states";
import type { Level } from "@/lib/types";

interface CompanionStatus {
  state: PulsiState;
  label: string;
  message: string;
}

function getStatus(disabled: boolean, consentRequired: boolean, running: boolean, chatError: boolean, level: Level | null, hasConversation: boolean): CompanionStatus {
  if (consentRequired) return {
    state: "privacy_shield",
    label: "CHAT IN PAUSA",
    message: "Per usare la chat, consulta il profilo e gestisci separatamente il consenso ai dati biometrici.",
  };
  if (running) return {
    state: "analyzing_whitebox",
    label: "STO ANALIZZANDO",
    message: "Esamino il messaggio e i dati disponibili, controllando anche incertezza e limiti.",
  };
  if (disabled) return {
    state: "pairing_sync",
    label: "CARICO IL PROFILO",
    message: "Sto verificando il profilo e la disponibilità dei dati demo.",
  };
  if (chatError) return {
    state: "puzzled",
    label: "CONNESSIONE INTERROTTA",
    message: "La risposta non è arrivata. Puoi riprovare; non ho elaborato una raccomandazione.",
  };
  if (level === "red") return {
    state: "critical_hitl_lock",
    label: "PRUDENZA",
    message: "Nei dati demo compare un segnale critico. Non è confermata alcuna revisione da parte di un professionista.",
  };
  if (level === "yellow") return {
    state: "fatigue_warning",
    label: "SEGNALI DA CONTESTUALIZZARE",
    message: "Alcuni segnali richiedono attenzione; considera il contesto e, se serve, chiedi un parere professionale.",
  };
  if (level === "green") return {
    state: "optimal",
    label: "QUADRO DEMO REGOLARE",
    message: "Nei dati demo non risultano segnali critici. Questo non è un via libera all'attività.",
  };
  if (level === "unknown") return {
    state: "puzzled",
    label: "DATI INSUFFICIENTI",
    message: "Mancano informazioni per una valutazione affidabile. La demo non colma i dati assenti.",
  };
  return {
    state: hasConversation ? "idle" : "welcome",
    label: hasConversation ? "IN ASCOLTO" : "CIAO, SONO PULSI",
    message: hasConversation
      ? "Sono qui per aiutarti a esplorare i dati, senza sostituire il tuo giudizio o un professionista."
      : "Ciao! Ti accompagno nella lettura dei dati e dei loro limiti.",
  };
}

export default function PulsiCompanion({ running, disabled, consentRequired, chatError, level, hasConversation }: {
  running: boolean;
  disabled: boolean;
  consentRequired: boolean;
  chatError: boolean;
  level: Level | null;
  hasConversation: boolean;
}) {
  const status = getStatus(disabled, consentRequired, running, chatError, level, hasConversation);

  return (
    <header className="pulsi-companion" aria-label="Stato dell'agente BioPulse">
      <div className="pulsi-companion-figure">
        <Pulsi state={status.state} size={88} trackCursor={false} title={`Pulsi: ${status.label.toLowerCase()}`} />
      </div>
      <div className="pulsi-companion-copy" aria-live="polite">
        <p className="pulsi-companion-eyebrow"><span className="pulsi-live-dot" /> BIOPULSE / COMPAGNO DIGITALE</p>
        <h2>Pulsi <span>·</span> {status.label}</h2>
        <p>{status.message}</p>
      </div>
      <div className="pulsi-companion-signal" aria-hidden="true">
        <span className="signal-bars"><i /><i /><i /><i /><i /><i /><i /></span>
        <small>{running ? "ELABORAZIONE" : consentRequired ? "IN ATTESA" : disabled ? "CARICAMENTO" : "DEMO · DATI SINTETICI"}</small>
      </div>
    </header>
  );
}
