"use client";
import { useCallback, useEffect, useState } from "react";
import { decideCase, getAlerts, getCases } from "@/lib/api";
import type { AlertItem, HitlCase } from "@/lib/types";
import { LEVEL } from "./level";

const STATUS = { pending: "In attesa", approved: "Approvato", modified: "Modificato e approvato", rejected: "Respinto" } as const;

function Case({ c, onDone }: { c: HitlCase; onDone: () => void }) {
  const [text, setText] = useState(c.draft_text);
  const [note, setNote] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const r = c.report, meta = LEVEL[c.level];
  const act = async (decision: "approve" | "modify" | "reject") => {
    setBusy(true); setErr(null);
    try { await decideCase(c.id, { decision, note: note || undefined, final_text: decision === "modify" ? text : undefined }); onDone(); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  return (
    <article className="rounded-lg border border-murex/30 bg-white p-4">
      <header className="flex flex-wrap items-baseline justify-between gap-2">
        <h4 className="font-display text-lg font-bold">{c.athlete_name ?? c.athlete_id} · caso #{c.id}</h4>
        <span className="rounded-full px-2.5 py-0.5 text-xs font-semibold" style={{ background: meta.soft, color: meta.color }}>{meta.label}</span>
      </header>
      <p className="mt-1 text-sm text-mute">Motivo: {c.trigger.replaceAll("_", " ").replaceAll("+", ", ")} · {new Date(c.created_at).toLocaleString("it-IT")}</p>
      <dl className="tnum mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        {[["ACWR", r.acwr], ["Z HRV", r.hrv_z], ["RMSSD (ms)", r.rmssd_ms], ["FC riposo", r.resting_hr]].map(([k, v]) => (
          <div key={String(k)} className="rounded bg-salt p-2"><dt className="text-xs text-mute">{k}</dt><dd className="font-semibold">{v ?? "–"}</dd></div>
        ))}
      </dl>
      <ul className="mt-2 list-disc pl-5 text-sm">{r.flags.filter(f => f.severity !== "info").map(f => <li key={f.code}>{f.message}</li>)}</ul>

      {c.status === "pending" ? (
        <div className="mt-3 space-y-2">
          <label className="block text-sm font-semibold" htmlFor={`d${c.id}`}>Bozza di protocollo (modificabile)</label>
          <textarea id={`d${c.id}`} value={text} onChange={e => setText(e.target.value)} rows={4} className="w-full rounded-lg border border-line p-2 text-sm" />
          <label className="block text-sm" htmlFor={`n${c.id}`}>Nota (obbligatoria se respingi)</label>
          <input id={`n${c.id}`} value={note} onChange={e => setNote(e.target.value)} className="w-full rounded-lg border border-line p-2 text-sm" />
          {err && <p role="alert" className="text-sm text-bad">{err}</p>}
          <div className="flex flex-wrap gap-2">
            <button disabled={busy} onClick={() => act("approve")} className="rounded-lg bg-murex px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Approva e invia all'atleta</button>
            <button disabled={busy || text === c.draft_text} onClick={() => act("modify")} className="rounded-lg border border-murex px-3 py-2 text-sm font-semibold text-murex disabled:opacity-40">Invia la versione modificata</button>
            <button disabled={busy} onClick={() => act("reject")} className="rounded-lg border border-line px-3 py-2 text-sm hover:border-bad">Respingi</button>
          </div>
        </div>
      ) : (
        <p className="mt-3 rounded bg-salt p-3 text-sm"><strong>{STATUS[c.status]}</strong> da {c.reviewer}. {c.final_text ?? c.reviewer_note}</p>
      )}
    </article>
  );
}

export default function HitlPanel({ refreshKey }: { refreshKey: number }) {
  const [cases, setCases] = useState<HitlCase[]>([]);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const load = useCallback(async () => {
    try { const [c, a] = await Promise.all([getCases(), getAlerts()]); setCases(c); setAlerts(a); setErr(null); }
    catch (e) { setErr((e as Error).message); }
  }, []);
  useEffect(() => { load(); const t = setInterval(load, 8000); return () => clearInterval(t); }, [load, refreshKey]);
  const pending = cases.filter(c => c.status === "pending"), done = cases.filter(c => c.status !== "pending");
  return (
    <div className="rounded-xl bg-murex-soft p-4 sm:p-6">
      {err && <p role="alert" className="mb-3 text-sm text-bad">{err}</p>}
      <h3 className="font-display text-xl font-bold text-murex">Da validare ({pending.length})</h3>
      <div className="mt-3 space-y-4">
        {pending.length === 0 && <p className="text-sm">Nessun caso in attesa. Quando l'agente rileva un rischio alto, apparirà qui prima di raggiungere l'atleta.</p>}
        {pending.map(c => <Case key={c.id} c={c} onDone={load} />)}
      </div>
      {done.length > 0 && (
        <details className="mt-5"><summary className="cursor-pointer font-semibold">Già valutati ({done.length})</summary>
          <div className="mt-3 space-y-3">{done.map(c => <Case key={c.id} c={c} onDone={load} />)}</div></details>
      )}
      {alerts.length > 0 && (
        <details className="mt-4"><summary className="cursor-pointer font-semibold">Avvisi inviati ({alerts.length})</summary>
          <ul className="mt-2 space-y-1 text-sm">{alerts.map(a => <li key={a.id}>{new Date(a.created_at).toLocaleTimeString("it-IT")} · {a.body} {a.simulated && <em className="text-mute">(simulato)</em>}</li>)}</ul></details>
      )}
    </div>
  );
}
