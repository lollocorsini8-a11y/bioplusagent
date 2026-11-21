"use client";

import { useCallback } from "react";
import { usePortal } from "@/components/PortalProvider";
import ChatPanel from "@/components/ChatPanel";
import HitlPanel from "@/components/HitlPanel";

export default function AssistantPage() {
  const { session, athleteId, data, refresh } = usePortal();
  const afterChat = useCallback(() => { void refresh(); }, [refresh]);
  return <main className="portal-content assistant-page">
    <div className="page-heading"><div><p className="eyebrow"><span className="live-dot" /> {session.user.role === "athlete" ? "CONVERSAZIONE ESPLICABILE" : "REVISIONE PROFESSIONALE"}</p>
      <h1>{session.user.role === "athlete" ? <>BioPulse <span className="heading-period">AI.</span></> : <>Area clinica<span className="heading-period">.</span></>}</h1>
      <p>{session.user.role === "athlete" ? "Parla di allenamento e recupero; chiedi spiegazioni e considera l'incertezza." : "Esamina i casi assegnati e registra una decisione professionale."}</p></div>
      <div className="assistant-badge"><span className="status-orb" /> {session.user.role === "athlete" ? "SUPPORTO, NON DIAGNOSI" : "REVISIONE CON SUPERVISIONE UMANA"}</div></div>
    {session.user.role === "athlete" && <div className="assistant-notice"><b>Prima di iniziare</b><span>L'agente può sbagliare e non è un professionista sanitario. In caso di sintomi urgenti, rivolgiti ai servizi di emergenza; non attendere una risposta dalla chat.</span></div>}
    {session.user.demo_guest && <div className="assistant-notice"><b>Beta pubblica</b><span>Usa solo gli scenari e i dati sintetici della demo. Non inserire nomi, contatti o informazioni sanitarie reali; gli avvisi a professionisti sono disattivati.</span></div>}
    {session.user.role === "athlete" ? (
      <ChatPanel athleteId={athleteId} disabled={!data || !data.athlete.consent_data}
        consentRequired={!!data && !data.athlete.consent_data} onInteraction={afterChat} level={data?.report.level ?? null} />
    ) : (
      <section className="clinician-section"><p className="eyebrow">SUPERVISIONE PROFESSIONALE</p><h2>Revisione HITL</h2>
        <p>Le proposte in attesa di revisione sono consultabili qui; la demo non garantisce una notifica al professionista.</p><HitlPanel refreshKey={0} />
      </section>
    )}
  </main>;
}
