"use client";

import { FormEvent, useEffect, useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getAuthOptions, getSession, login, registerAthlete, startDemo } from "@/lib/api";

function authError(reason: unknown) {
  const failure = reason as { message?: string };
  return failure.message === "Failed to fetch"
    ? "Servizio di accesso non raggiungibile. Verifica che il backend sia avviato."
    : failure.message ?? "Accesso non riuscito. Riprova.";
}

export default function Home() {
  const router = useRouter();
  const reduceMotion = useReducedMotion();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [name, setName] = useState("");
  const [registerMode, setRegisterMode] = useState(false);
  const [registrationEnabled, setRegistrationEnabled] = useState(false);
  const [publicDemoEnabled, setPublicDemoEnabled] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getAuthOptions().then(value => {
      if (active) {
        setRegistrationEnabled(value.self_registration);
        setPublicDemoEnabled(value.public_demo);
      }
    })
      .catch(reason => { if (active) setError(authError(reason)); });
    getSession().then(session => {
      if (active) router.replace(localStorage.getItem(`biopulse-onboarding:${session.user.id}`) === "complete" ? "/dashboard" : "/onboarding");
    }).catch(reason => {
      if (active && (reason as { status?: number }).status !== 401) setError(authError(reason));
    });
    return () => { active = false; };
  }, [router]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");
    if (registerMode && password !== confirmation) { setError("Le password non coincidono."); return; }
    setBusy(true);
    try {
      if (registerMode) await registerAthlete(email, password, name, "standard");
      else await login(email, password);
      const session = await getSession();
      router.replace(localStorage.getItem(`biopulse-onboarding:${session.user.id}`) === "complete" ? "/dashboard" : "/onboarding");
    } catch (reason) {
      setError(authError(reason));
    } finally { setBusy(false); }
  }

  async function beginDemo() {
    setError("");
    setBusy(true);
    try {
      await startDemo();
      router.replace("/onboarding");
    } catch (reason) {
      setError(authError(reason));
    } finally { setBusy(false); }
  }

  return (
    <main className="auth-page">
      <div className="auth-left">
        <Link href="/" className="brand-lockup auth-brand">
          <span className="brand-mark"><span /></span>
          <span className="brand-word">bio<span>pulse</span><small>ATHLETE INTELLIGENCE</small></span>
        </Link>
        <div className="auth-copy">
          <motion.div initial={reduceMotion ? false : { opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .7 }}>
            <p className="eyebrow"><span className="live-dot" /> SCIENZA DEL MOVIMENTO, SPIEGATA</p>
            <h1>Ascolta i segnali.<br /><span>Comprendi il tuo</span><br />recupero.</h1>
            <p className="auth-intro">Un compagno digitale che rende leggibili i dati di allenamento e recupero. Le decisioni restano sempre tue, insieme ai professionisti che ti seguono.</p>
          </motion.div>
          <div className="pulse-art" aria-label="Illustrazione astratta di un segnale biologico">
            <div className="pulse-orbit orbit-one" /><div className="pulse-orbit orbit-two" />
            <motion.div className="pulse-core" animate={reduceMotion ? undefined : { scale: [1, 1.08, 1] }} transition={{ duration: 4, repeat: Infinity, ease: "easeInOut" }}>
              <span className="brand-mark pulse-logo"><span /></span>
            </motion.div>
            <svg className="pulse-line" viewBox="0 0 640 130" role="presentation" preserveAspectRatio="none">
              <path d="M0 70h125l24-2 17 2 20-6 15 9 23-19 20 48 27-85 26 72 22-27 21 9 24-1h276" />
            </svg>
            <span className="pulse-label label-left">SEGNALI</span><span className="pulse-label label-right">CONSAPEVOLEZZA</span>
          </div>
          <div className="auth-trust"><span>01 / DATI TRASPARENTI</span><span>02 / CONTROLLO UMANO</span><span>03 / PROTOTIPO ETICO</span></div>
        </div>
        <div className="auth-footnote">BioPulse-Agent · prototipo dimostrativo, non dispositivo medico</div>
      </div>
      <section className="auth-right" aria-labelledby="login-title">
        <div className="auth-form-wrap">
          <div className="auth-mobile-brand brand-lockup">
            <span className="brand-mark"><span /></span><span className="brand-word">bio<span>pulse</span><small>ATHLETE INTELLIGENCE</small></span>
          </div>
          <p className="auth-kicker">IL TUO SPAZIO PERSONALE</p>
          <h2 id="login-title">{registerMode ? "Inizia da qui." : "Bentornato."}</h2>
          <p className="form-caption">{registerMode ? "Crea un account atleta per la demo locale." : "Accedi per esplorare il tuo spazio BioPulse."}</p>
          {error && <p role="alert" className="form-error">{error}</p>}
          <form onSubmit={submit} className="auth-form">
            {registerMode && <label>Nome visualizzato
              <input required maxLength={120} autoComplete="name" value={name} onChange={event => setName(event.target.value)} placeholder="Come vuoi essere chiamato?" />
            </label>}
            <label>Email
              <input required type="email" autoComplete="username" value={email} onChange={event => setEmail(event.target.value)} placeholder="nome@email.it" />
            </label>
            <label>Password
              <input required type="password" minLength={registerMode ? 12 : 1} autoComplete={registerMode ? "new-password" : "current-password"} value={password} onChange={event => setPassword(event.target.value)} placeholder={registerMode ? "Almeno 12 caratteri" : "La tua password"} />
            </label>
            {registerMode && <label>Conferma password
              <input required type="password" minLength={12} autoComplete="new-password" value={confirmation} onChange={event => setConfirmation(event.target.value)} placeholder="Ripeti la password" />
            </label>}
            <button type="submit" className="button-primary auth-submit" disabled={busy}>
              {busy ? "Un momento…" : registerMode ? "Crea account atleta" : "Accedi al portale"} <span aria-hidden>↗</span>
            </button>
          </form>
          {publicDemoEnabled && <div className="demo-entry">
            <p>Vuoi esplorare il prototipo? Avvia una sessione ospite isolata, senza account e con dati esclusivamente sintetici.</p>
            <button type="button" className="button-secondary" disabled={busy} onClick={beginDemo}>
              {busy ? "Preparo la demo…" : "Prova la beta con dati sintetici"} <span aria-hidden>↗</span>
            </button>
            <small>Non inserire dati personali o sanitari reali. Sessione temporanea; nessun avviso viene inviato.</small>
          </div>}
          {registrationEnabled && <button className="auth-toggle" onClick={() => { setRegisterMode(!registerMode); setError(""); }}>
            {registerMode ? "Hai già un account? Accedi" : "Nuovo alla demo? Crea un account atleta"}
          </button>}
          <div className="auth-disclaimer">
            <span className="disclaimer-icon">i</span><p>I dati biometrici sono facoltativi e il consenso si gestisce separatamente. La demo usa dati sintetici e non invia notifiche a professionisti.</p>
          </div>
          <div className="auth-links"><Link href="/privacy">Informativa prototipale</Link><Link href="/cookies">Cookie tecnici</Link><Link href="/ethics">Etica e limiti</Link></div>
        </div>
        <div className="auth-side-index">BPA / 01 <span>ACCESSO</span></div>
      </section>
    </main>
  );
}
