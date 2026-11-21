"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";
import { usePortal } from "@/components/PortalProvider";
import LoadChart from "@/components/LoadChart";
import MetricCard from "@/components/MetricCard";
import ReadinessRing from "@/components/ReadinessRing";

export default function DashboardPage() {
  const { session, data, error, loading } = usePortal();
  const reduceMotion = useReducedMotion();
  const report = data?.report;
  const series = data?.series ?? [];
  const values = <K extends keyof (typeof series)[number]>(key: K) => series.map(point => point[key] as number | null);
  return (
    <main className="portal-content">
      <motion.div className="page-heading" initial={reduceMotion ? false : { opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <div><p className="eyebrow"><span className="live-dot" /> IL TUO QUADRO DI OGGI</p>
          <h1>Ciao, {data?.athlete.name ?? session.athletes[0]?.name ?? "atleta"}<span className="heading-period">.</span></h1>
          <p>Un punto di partenza per osservare il recupero, non un verdetto sul tuo stato di salute.</p>
        </div>
        <Link href="/assistant" className="button-primary heading-action">
          {session.user.role === "athlete" ? "Parla con BioPulse" : "Apri l'area clinica"} <span>↗</span>
        </Link>
      </motion.div>
      <div className="demo-banner"><span>i</span><p><b>Ambiente dimostrativo.</b> Dati e wearable sono simulati; indicatori e soglie non sono validati clinicamente.</p>
        {(session.demo_mode || session.user.demo_guest) && <Link href="/profile">Scegli uno scenario ↗</Link>}
        <Link href="/ethics">Scopri i limiti ↗</Link>
      </div>
      {error && <p role="alert" className="form-error">{error}</p>}
      {loading && !data && <div className="dashboard-loading">Caricamento dei dati dimostrativi…</div>}
      {data && report && <>
        <section className="dashboard-grid" aria-label="Riepilogo biometrico">
          <div className="readiness-panel">
            <div className="section-label"><span>01</span> PRONTEZZA INDICATIVA</div>
            <ReadinessRing report={report} compact />
            <div className="confidence-label"><span className="confidence-dot" /> Confidenza {report.confidence === "full" ? "completa" : report.confidence === "partial" ? "parziale" : "insufficiente"} · {report.data_days} giorni con dati</div>
          </div>
          <div className="metrics-panel">
            <div className="section-label"><span>02</span> SEGNALI E TREND <small>DATI SINTETICI</small></div>
            <div className="metrics-grid">
              <MetricCard label="HRV · RMSSD" value={report.rmssd_ms?.toFixed(0) ?? "–"} unit="ms" values={values("rmssd_ms")}
                hint={report.hrv_z !== null ? `Z-score ${report.hrv_z > 0 ? "+" : ""}${report.hrv_z}` : "baseline in costruzione"} tone={report.hrv_z !== null && report.hrv_z < -1.5 ? "#B3261E" : "#1D6B80"} />
              <MetricCard label="ACWR" value={report.acwr?.toFixed(2) ?? "–"} values={series.map(point => point.load)}
                hint={report.acwr !== null ? "soglie demo, non validate" : "dato non disponibile"} tone={report.acwr !== null && report.acwr > 1.5 ? "#B3261E" : "#1D6B80"} />
              <MetricCard label="Efficienza del sonno" value={report.sleep_efficiency?.toFixed(0) ?? "–"} unit="%" values={values("sleep_efficiency")} hint={`${series.at(-1)?.sleep_hours ?? "–"} h · ultima notte`} />
              <MetricCard label="Temperatura cutanea" value={series.at(-1)?.skin_temp_c?.toFixed(1) ?? "–"} unit="°C" values={values("skin_temp_c")} hint={`FC a riposo ${report.resting_hr?.toFixed(0) ?? "–"} bpm`} />
            </div>
          </div>
        </section>
        <section className="chart-section"><div className="section-label"><span>03</span> CARICO E RECUPERO <small>STORICO SIMULATO</small></div><LoadChart series={series} report={report} /></section>
        <section className="next-step-card"><div className="next-step-symbol">✳</div><div><p className="eyebrow">{session.user.role === "athlete" ? "ESPLORA CONTESTO E INCERTEZZA" : "REVISIONE PROFESSIONALE"}</p><h2>{session.user.role === "athlete" ? "Un numero da solo non basta." : "Contesto prima della revisione."}</h2><p>{session.user.role === "athlete" ? "Chiedi all'agente di spiegare i segnali e le informazioni che mancano. Non sostituisce un parere medico." : "Apri l'area clinica per esaminare i casi disponibili."}</p></div><Link href="/assistant" className="text-link">{session.user.role === "athlete" ? "Apri la chat" : "Apri revisione"} <span>→</span></Link></section>
      </>}
    </main>
  );
}
