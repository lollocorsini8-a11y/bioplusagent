"use client";

import { FormEvent, useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getSession, seedDemo, setConsent } from "@/lib/api";
import type { SessionInfo } from "@/lib/types";

const STEPS = ["Il tuo spazio", "Connessioni", "Privacy", "Inizia"];

export default function OnboardingPage() {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [session, setSession] = useState<SessionInfo | null>(null);
  const [step, setStep] = useState(0);
  const [contact, setContact] = useState("");
  const [readPrivacy, setReadPrivacy] = useState(false);
  const [syntheticConsent, setSyntheticConsent] = useState(false);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [preferencesLoaded, setPreferencesLoaded] = useState(false);

  useEffect(() => {
    let active = true;
    getSession().then(value => {
      if (!active) return;
      setSession(value);
      if (localStorage.getItem(`biopulse-onboarding:${value.user.id}`) === "complete") router.replace("/dashboard");
      const savedStep = Number(localStorage.getItem(`biopulse-onboarding-step:${value.user.id}`));
      if (Number.isInteger(savedStep) && savedStep >= 0 && savedStep < STEPS.length) setStep(savedStep);
      setContact(localStorage.getItem(`biopulse-coach-contact:${value.user.id}`) ?? "");
      setReadPrivacy(localStorage.getItem(`biopulse-privacy-read:${value.user.id}`) === "true");
      setPreferencesLoaded(true);
    }).catch(() => { if (active) router.replace("/"); });
    return () => { active = false; };
  }, [router]);

  useEffect(() => {
    if (!session || !preferencesLoaded) return;
    localStorage.setItem(`biopulse-onboarding-step:${session.user.id}`, String(step));
    localStorage.setItem(`biopulse-coach-contact:${session.user.id}`, contact);
    localStorage.setItem(`biopulse-privacy-read:${session.user.id}`, String(readPrivacy));
  }, [session, preferencesLoaded, step, contact, readPrivacy]);

  async function finish(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!session) return;
    if (!readPrivacy) { setError("Per continuare, conferma di aver consultato le informative prototipali."); return; }
    if (session.user.demo_guest && !syntheticConsent) {
      setError("Per continuare, autorizza esplicitamente l'uso dei dati simulati nella demo.");
      return;
    }
    setError("");
    setSaving(true);
    try {
      if (session.user.demo_guest) {
        if (!athlete) throw new Error("Non trovo il profilo ospite della demo. Riprova dall'inizio.");
        await setConsent(athlete.id, { consent_data: true });
        await seedDemo(athlete.id, "overload");
      } else {
        localStorage.setItem(`biopulse-coach-contact:${session.user.id}`, contact.trim());
      }
      localStorage.setItem("biopulse-cookie-choice", "necessary-only");
      localStorage.setItem(`biopulse-privacy-read:${session.user.id}`, "true");
      localStorage.setItem(`biopulse-onboarding:${session.user.id}`, "complete");
      router.replace("/dashboard");
    } catch (reason) {
      setError((reason as Error).message || "Non riesco ad avviare la demo. Riprova.");
    } finally { setSaving(false); }
  }

  if (!session) return <div className="portal-loading"><span className="brand-mark brand-mark-small" />Verifica accesso…</div>;
  const athlete = session.athletes[0];
  return (
    <main className="onboarding-page">
      <header className="onboarding-header">
        <Link href="/" className="brand-lockup"><span className="brand-mark"><span /></span><span className="brand-word">bio<span>pulse</span><small>ATHLETE INTELLIGENCE</small></span></Link>
        <span className="onboarding-step-label">CONFIGURAZIONE INIZIALE <b>0{step + 1} / 04</b></span>
      </header>
      <div className="onboarding-progress" aria-label={`Passaggio ${step + 1} di 4`}><span style={{ width: `${(step + 1) * 25}%` }} /></div>
      <div className="onboarding-grid">
        <div className="onboarding-main">
          <div className="step-dots" aria-hidden>{STEPS.map((item, index) => <span key={item} className={index <= step ? "step-dot done" : "step-dot"} />)}</div>
          {step === 0 && <motion.section key="intro" initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <p className="eyebrow"><span className="live-dot" /> BENVENUTO, {athlete?.name?.toUpperCase() ?? "ATLETA"}</p>
            <h1 className="onboarding-title">Il tuo corpo parla.<br /><span>Impariamo ad ascoltarlo.</span></h1>
            <p className="onboarding-lead">BioPulse organizza segnali di allenamento e recupero in una vista comprensibile. Non fa diagnosi, non sostituisce il tuo giudizio né quello di un professionista.</p>
            <div className="intro-cards">
              <article><span>01</span><b>Osserva</b><p>Esplora metriche, trend e qualità dei dati senza trasformare un numero in una diagnosi.</p></article>
              <article><span>02</span><b>Comprendi</b><p>Chiedi all'agente di spiegare i segnali e le incertezze che li accompagnano.</p></article>
              <article><span>03</span><b>Decidi con consapevolezza</b><p>Usa le informazioni come supporto, confrontandoti con il tuo team quando serve.</p></article>
            </div>
            <button className="button-primary onboarding-next" onClick={() => setStep(1)}>Configura il prototipo <span>→</span></button>
          </motion.section>}
          {step === 1 && <motion.section key="connections" initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <p className="eyebrow">01 — CONNESSIONI E PROFILO</p><h1 className="onboarding-title">Partiamo da ciò<br /><span>che è davvero attivo.</span></h1>
            <div className="connection-card">
              <div className="connection-icon">⌁</div><div><h2>Wearable</h2><p>Il collegamento a orologi reali non è attivo. Puoi provare dati e sincronizzazione <strong>interamente simulati</strong> dal profilo.</p></div><span className="connection-status">SIMULATO</span>
            </div>
            <div className="connection-card">
              <div className="connection-icon">◎</div><div><h2>Allenatore o professionista</h2><p>Il contatto non è collegato a messaggi o notifiche. Se lo inserisci, resta salvato solo in questo browser e non viene contattato.</p>
              {!session.user.demo_guest
                ? <label className="contact-label">Contatto (facoltativo)
                  <input value={contact} onChange={event => setContact(event.target.value)} maxLength={160} placeholder="Nome, email o numero — solo promemoria locale" />
                </label>
                : <p className="text-sm text-mute">Nella beta pubblica non inserire contatti personali: nessun professionista è collegato.</p>}
              </div><span className="connection-status inactive">NON COLLEGATO</span>
            </div>
            <div className="setup-note"><b>Profilo: {athlete?.profile ?? "standard"}</b> — i profili sono descrittivi e non modificano le formule. Il contatto professionista non abilita condivisione di dati.</div>
            <div className="onboarding-actions"><button className="button-quiet" onClick={() => setStep(0)}>← Indietro</button><button className="button-primary" onClick={() => setStep(2)}>Continua <span>→</span></button></div>
          </motion.section>}
          {step === 2 && <motion.section key="privacy" initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <p className="eyebrow">02 — INFORMAZIONI E PREFERENZE</p><h1 className="onboarding-title">Prima di entrare,<br /><span>conosci i confini.</span></h1>
            <p className="onboarding-lead">Questi testi descrivono il prototipo attuale, non sono informative legali definitive. Devono essere verificati da professionisti privacy e legali prima di un uso reale.</p>
            <div className="policy-links">
              <Link href="/privacy"><span>01</span><b>Privacy e trattamento dei dati</b><small>Finalità, dati biometrici, conservazione e cancellazione ↗</small></Link>
              <Link href="/cookies"><span>02</span><b>Cookie e archiviazione locale</b><small>Cookie tecnici e preferenze salvate nel browser ↗</small></Link>
              <Link href="/ethics"><span>03</span><b>Etica, limiti e possibili bias</b><small>Limiti di validazione, inclusione e supervisione ↗</small></Link>
            </div>
            <div className="cookie-choice"><span className="cookie-lock">▣</span><div><b>Solo archiviazione necessaria</b><p>Autenticazione e protezione CSRF richiedono cookie tecnici. Non risultano cookie analytics o pubblicitari: non c'è un'opzione “accetta tutti”.</p></div><span className="required-pill">NECESSARI</span></div>
            {error && <p role="alert" className="form-error">{error}</p>}
            <label className="privacy-check"><input type="checkbox" checked={readPrivacy} onChange={event => { setReadPrivacy(event.target.checked); setError(""); }} />
              <span>Confermo di aver consultato i testi prototipali e scelgo di proseguire nella demo con i soli strumenti tecnici necessari. Ho capito che non è un consenso a usare dati biometrici.</span>
            </label>
            {session.user.demo_guest && <label className="privacy-check"><input type="checkbox" checked={syntheticConsent} onChange={event => { setSyntheticConsent(event.target.checked); setError(""); }} />
              <span>Autorizzo BioPulse a elaborare, per questa sessione ospite, esclusivamente i dati biometrici simulati del profilo demo. Non userò né inserirò dati personali o sanitari reali; posso interrompere la sessione in qualsiasi momento.</span>
            </label>}
            <div className="onboarding-actions"><button className="button-quiet" onClick={() => setStep(1)}>← Indietro</button><button className="button-primary" disabled={!readPrivacy} onClick={() => { setError(""); setStep(3); }}>Continua <span>→</span></button></div>
          </motion.section>}
          {step === 3 && <motion.section key="tour" initial={reduceMotion ? false : { opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
            <p className="eyebrow"><span className="live-dot" /> ORIENTAMENTO · 30 SECONDI</p><h1 className="onboarding-title">Un portale.<br /><span>Tre prospettive.</span></h1>
            {session.user.demo_guest && <p className="onboarding-lead">Avvieremo un profilo temporaneo con 42 giorni di dati sintetici nello scenario di carico elevato. Dalla pagina Profilo potrai scegliere anche equilibrio, calo della HRV o settimana di scarico. Nessun dispositivo, contatto o dato reale è collegato.</p>}
            <div className="tour-visual" aria-hidden><div className="tour-ring ring-a" /><div className="tour-ring ring-b" /><div className="tour-center"><span className="brand-mark"><span /></span></div><i className="tour-node node-a" /><i className="tour-node node-b" /><i className="tour-node node-c" /></div>
            <div className="tour-list"><p><b>01 / Panoramica</b><span>metriche, trend, livello di completezza e fonti demo.</span></p><p><b>02 / BioPulse AI</b><span>chat esplicabile, con tracciamento dei passaggi e limiti dichiarati.</span></p><p><b>03 / Profilo</b><span>consenso biometrico separato, scelta fra quattro scenari sintetici e strumenti di cancellazione.</span></p></div>
            {error && <p role="alert" className="form-error">{error}</p>}
            <form onSubmit={finish}><div className="onboarding-actions"><button type="button" className="button-quiet" onClick={() => setStep(2)}>← Rileggi informative</button><button type="submit" className="button-primary" disabled={saving}>{saving ? "Preparo il profilo…" : "Entra nella demo"} <span>↗</span></button></div></form>
          </motion.section>}
        </div>
        <aside className="onboarding-aside">
          <div className="aside-pulse"><span className="brand-mark"><span /></span><div className="aside-wave" /></div>
          <p className="aside-index">BIOPULSE / ORIENTAMENTO</p><h2>La tecnologia<br />come alleata.<br /><em>Mai come verdetto.</em></h2>
          <p>Un punteggio non racconta tutta la persona. Tieni conto del contesto, dei tuoi sintomi e della voce dei professionisti.</p>
          <div className="aside-disclaimer"><span>!</span><p>Prototipo non validato clinicamente.<br />Non usare per diagnosi o decisioni urgenti.</p></div>
        </aside>
      </div>
    </main>
  );
}
