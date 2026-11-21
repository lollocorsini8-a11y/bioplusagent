"use client";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import type { TraceEvent } from "@/lib/types";

const KIND: Record<string, { tag: string; solid: boolean }> = {
  input_check: { tag: "calcolato", solid: true }, consent: { tag: "calcolato", solid: true },
  perception: { tag: "misurato", solid: true }, whitebox: { tag: "calcolato", solid: true },
  safety: { tag: "calcolato", solid: true }, self_check: { tag: "calcolato", solid: true }, hitl: { tag: "calcolato", solid: true },
  subjective: { tag: "dal tuo testo", solid: false }, memory: { tag: "storico", solid: true },
  rag: { tag: "letteratura", solid: false }, llm: { tag: "interpretato dal modello", solid: false },
  internal_error: { tag: "errore gestito", solid: true },
};
const MARK = { ok: "✓", warn: "!", error: "✕" } as const;
const TONE = { ok: "#2F7D5B", warn: "#9A6200", error: "#B3261E" } as const;

function Values({ d }: { d: Record<string, unknown> }) {
  const keys: [string, string][] = [["acwr", "ACWR"], ["rmssd_ms", "RMSSD"], ["hrv_z", "Z HRV"], ["readiness", "Prontezza"]];
  const shown = keys.filter(([k]) => d[k] !== undefined && d[k] !== null);
  if (!shown.length) return null;
  return (
    <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs">
      {shown.map(([k, label]) => (
        <div key={k} className="flex gap-1"><dt className="text-mute">{label}</dt><dd className="tnum font-semibold">{String(d[k])}</dd></div>
      ))}
    </dl>
  );
}

export default function ThoughtTrace({ events, running }: { events: TraceEvent[]; running: boolean }) {
  const reduce = useReducedMotion();
  return (
    <section aria-label="Traccia di ragionamento dell'agente" className="rounded-xl border border-line bg-paper p-4">
      <div className="mb-3 flex items-baseline justify-between gap-2">
        <h3 className="font-display text-lg font-bold">Come ha ragionato l'agente</h3>
        {running && <span className="text-sm text-sea" role="status">in corso…</span>}
      </div>
      <p className="mb-3 text-xs text-mute">Linea piena: dato misurato o calcolato con formule. Linea tratteggiata: testo interpretato dal modello o dalla letteratura.</p>
      {events.length === 0 ? (
        <p className="text-sm text-mute">Scrivi un messaggio: qui vedrai ogni passaggio, dai dati del dispositivo ai controlli di sicurezza.</p>
      ) : (
        <ol className="space-y-2" aria-live="polite">
          <AnimatePresence initial={false}>
            {events.map((e, i) => {
              const k = KIND[e.step] ?? { tag: e.step, solid: true };
              return (
                <motion.li key={i} initial={reduce ? false : { opacity: 0, x: -8 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.18 }}
                  className="rounded-md bg-salt p-3 pl-4" style={{ borderLeft: `3px ${k.solid ? "solid" : "dashed"} ${TONE[e.status]}` }}>
                  <div className="flex items-start gap-2">
                    <span aria-hidden className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full text-xs text-white" style={{ background: TONE[e.status] }}>{MARK[e.status]}</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold">{e.title}</p>
                      <p className="break-words text-sm text-ink/80">{e.detail}</p>
                      <Values d={e.data} />
                    </div>
                    <div className="shrink-0 text-right text-xs text-mute"><p>{k.tag}</p><p className="tnum">{e.t_ms} ms</p></div>
                  </div>
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ol>
      )}
    </section>
  );
}
