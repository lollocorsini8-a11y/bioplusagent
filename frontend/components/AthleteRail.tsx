"use client";
import { useState } from "react";
import type { Dashboard, Scenario } from "@/lib/types";
import { eraseData, getDashboard, seedDemo, setConsent, syncWearable } from "@/lib/api";

const SCENARIOS: { id: Scenario; title: string; text: string }[] = [
  { id: "normal", title: "Atleta in equilibrio", text: "Carico stabile, HRV nella norma." },
  { id: "overload", title: "Sovraccarico", text: "Ultima settimana quasi doppia: ACWR in zona di pericolo." },
  { id: "hrv_drop", title: "Calo della HRV", text: "Carico regolare ma HRV in forte calo da 3 giorni." },
  { id: "recovery", title: "Settimana di scarico", text: "Carico ridotto dopo un blocco intenso." },
];

export default function AthleteRail({ data, athleteId, canManage, demoMode, isPublicDemo, onChange, onReset }: {
  data: Dashboard | null; athleteId: string; canManage: boolean; demoMode: boolean; isPublicDemo: boolean;
  onChange: (d: Dashboard) => void; onReset: () => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  async function load(s: Scenario) {
    setBusy(s); setMsg(null);
    try { onChange(await seedDemo(athleteId, s)); }
    catch (e) { setMsg((e as Error).message); } finally { setBusy(null); }
  }
  async function synchronizeWearable() {
    setBusy("wearable"); setMsg(null);
    try {
      const result = await syncWearable(athleteId);
      onChange(await getDashboard(athleteId));
      setMsg(`Fonte sintetica sincronizzata: ${result.records_accepted} record riletti, ultimo giorno ${result.cursor_day}.`);
    } catch (e) { setMsg((e as Error).message); }
    finally { setBusy(null); }
  }
  async function consent(k: "consent_data" | "consent_alerts", v: boolean) {
    if (!data) return;
    try { await setConsent(athleteId, k === "consent_data" ? { consent_data: v } : { consent_alerts: v }); onChange({ ...data, athlete: { ...data.athlete, [k]: v } }); }
    catch (e) { setMsg((e as Error).message); }
  }
  async function erase(scope: "memory" | "all") {
    const ok = window.confirm(scope === "all"
      ? "Cancellare profilo, account e tutti i dati associati (metriche, memoria, casi, avvisi e consensi)? L'azione è definitiva."
      : "Cancellare la memoria dell'agente su questo atleta?");
    if (!ok) return;
    try { await eraseData(athleteId, scope); setMsg(scope === "all" ? "Tutti i dati sono stati cancellati." : "Memoria dell'agente cancellata."); if (scope === "all") onReset(); }
    catch (e) { setMsg((e as Error).message); }
  }

  return (
    <aside className="space-y-6 text-sm" aria-label="Profilo e dati demo">
      <div>
        <p className="text-mute">Atleta</p>
        <p className="font-display text-xl font-bold">{data?.athlete.name ?? "—"}</p>
        <p className="text-mute">{data?.athlete.profile === "standard" ? "Profilo standard" : data?.athlete.profile}</p>
      </div>

      {canManage && demoMode && <fieldset className="space-y-2">
        <legend className="mb-2 font-semibold">Sincronizzazione wearable</legend>
        <p className="text-xs text-mute">Sorgente sintetica di test: nessun dispositivo o dato personale collegato.</p>
        <button onClick={synchronizeWearable} disabled={busy !== null || !data?.athlete.consent_data}
          className="w-full rounded-lg bg-sea px-3 py-2 text-left font-semibold text-white hover:bg-sea-dark disabled:opacity-50">
          {busy === "wearable" ? "Sincronizzo…" : "Sincronizza wearable simulato"}
        </button>
      </fieldset>}

      {canManage && demoMode && <fieldset>
        <legend className="mb-2 font-semibold">Scenario di dati simulati</legend>
        <div className="space-y-2">
          {SCENARIOS.map(s => (
            <button key={s.id} onClick={() => load(s.id)} disabled={busy !== null || !data?.athlete.consent_data}
              className="w-full rounded-lg border border-line bg-paper p-3 text-left transition hover:border-sea disabled:opacity-60">
              <span className="block font-semibold">{busy === s.id ? "Carico…" : s.title}</span>
              <span className="block text-mute">{s.text}</span>
            </button>
          ))}
        </div>
      </fieldset>}

      {canManage && <fieldset className="space-y-2">
        <legend className="mb-2 font-semibold">Consenso biometrico e avvisi</legend>
        <label className="flex items-start gap-2"><input type="checkbox" disabled={!data} className="mt-1 h-4 w-4 accent-[#1D6B80]" checked={!!data?.athlete.consent_data} onChange={e => consent("consent_data", e.target.checked)} />
          <span>Autorizzo l'analisi dei miei dati biometrici</span></label>
        {!isPublicDemo && <label className="flex items-start gap-2"><input type="checkbox" disabled={!data} className="mt-1 h-4 w-4 accent-[#1D6B80]" checked={!!data?.athlete.consent_alerts} onChange={e => consent("consent_alerts", e.target.checked)} />
          <span>Autorizzo gli avvisi tramite il canale configurato dal gestore</span></label>}
        <p className="text-xs text-mute">{isPublicDemo
          ? "Nella beta pubblica i dati sono sintetici e gli avvisi esterni sono disattivati."
          : "Il contatto salvato in questo browser non è collegato. L'eventuale invio esterno dipende dalla configurazione server; questa scelta tecnica non sostituisce un consenso o un'informativa legale."}</p>
      </fieldset>}

      {canManage && <div className="space-y-2">
        <button onClick={() => erase("memory")} className="w-full rounded-lg border border-line px-3 py-2 text-left hover:border-bad">Cancella la memoria dell'agente</button>
        <button onClick={() => erase("all")} className="w-full rounded-lg border border-line px-3 py-2 text-left text-bad hover:border-bad">Cancella tutti i miei dati</button>
      </div>}
      {msg && <p role="status" className="rounded-lg bg-sea-soft p-3">{msg}</p>}
    </aside>
  );
}
