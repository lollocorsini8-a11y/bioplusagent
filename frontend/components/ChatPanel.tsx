"use client";
import { useEffect, useRef, useState } from "react";
import { getValidated, streamChat } from "@/lib/api";
import type { HitlCase, Level, MessageEvent, TraceEvent } from "@/lib/types";
import ThoughtTrace from "./ThoughtTrace";
import PulsiCompanion from "./PulsiCompanion";

interface Msg { role: "user" | "agent"; text: string; meta?: MessageEvent }

const QUICK = ["Come mi alleno oggi?", "Ho dormito male, RPE 7 ieri", "Sto benissimo, voglio fare ripetute massimali", "Ho dolore al petto mentre corro"];
const SOURCE: Record<string, string> = {
  llm: "risposta del modello, controllata", deterministic: "risposta generata dalle regole",
  guardrail: "risposta sostituita per sicurezza",
  safety: "protocollo di sicurezza", fallback: "modalità di riserva", "safe-mode": "modalità sicura", system: "sistema",
};

export default function ChatPanel({ athleteId, disabled, consentRequired = false, onInteraction, level = null }: {
  athleteId: string;
  disabled: boolean;
  consentRequired?: boolean;
  onInteraction: () => void;
  level?: Level | null;
}) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [trace, setTrace] = useState<TraceEvent[]>([]);
  const [input, setInput] = useState("");
  const [running, setRunning] = useState(false);
  const [failure, setFailure] = useState("");
  const [validated, setValidated] = useState<HitlCase[]>([]);
  const [chatError, setChatError] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ block: "nearest" }); }, [msgs]);
  useEffect(() => {
    let alive = true;
    const load = () => getValidated(athleteId).then(v => alive && setValidated(v)).catch(() => undefined);
    load(); const t = setInterval(load, 8000);
    return () => { alive = false; clearInterval(t); };
  }, [athleteId]);

  async function send(text: string) {
    if (running) return;
    setMsgs(m => [...m, { role: "user", text: text.trim() || "(messaggio vuoto)" }]);
    setInput(""); setTrace([]); setChatError(false); setRunning(true);
    try {
      await streamChat({ athlete_id: athleteId, message: text, simulate_failure: failure }, e => {
        if (e.type === "trace") setTrace(t => [...t, e]);
        else if (e.type === "message") setMsgs(m => [...m, { role: "agent", text: e.text, meta: e }]);
      });
    } catch (err) {
      setChatError(true);
      setMsgs(m => [...m, { role: "agent", text: (err as Error).message }]);
    } finally { setRunning(false); onInteraction(); }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <section aria-label="Conversazione con l'agente" className="chat-surface flex h-[34rem] flex-col rounded-xl border border-line bg-paper">
        <PulsiCompanion running={running} disabled={disabled} consentRequired={consentRequired} chatError={chatError} level={level} hasConversation={msgs.length > 0} />
        <div className="flex-1 space-y-3 overflow-y-auto p-4" aria-live="polite">
          {msgs.length === 0 && (
            <div className="text-sm text-mute">
              <p className="mb-3">Racconta come ti senti o chiedi cosa fare oggi. Puoi anche provare uno di questi messaggi:</p>
              <div className="flex flex-wrap gap-2">
                {QUICK.map(q => <button key={q} disabled={disabled || running} onClick={() => send(q)}
                  className="rounded-full border border-line px-3 py-1.5 text-left text-ink hover:border-sea disabled:opacity-50">{q}</button>)}
              </div>
            </div>
          )}
          {msgs.map((m, i) => (
            <div key={i} className={m.role === "user" ? "ml-10 rounded-lg bg-sea p-3 text-white" : "mr-6 rounded-lg bg-salt p-3"}>
              <p className="whitespace-pre-wrap text-[15px] leading-relaxed">{m.text}</p>
              {m.meta && (
                <p className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-mute">
                  <span>{SOURCE[m.meta.source] ?? m.meta.source}</span>
                  {m.meta.held && <span className="font-semibold text-murex">piano personalizzato non fornito · revisione professionale non garantita</span>}
                </p>
              )}
            </div>
          ))}
          <div ref={endRef} />
        </div>

        {validated.length > 0 && (
          <div className="border-t border-line bg-murex-soft p-3 text-sm">
            <p className="font-semibold text-murex">Dal tuo medico o preparatore</p>
            {validated.slice(0, 2).map(v => (
              <p key={v.id} className="mt-1">
                {v.status === "rejected" ? `Il tuo professionista ha chiesto di rivedere il piano: ${v.reviewer_note}` : v.final_text}
              </p>
            ))}
          </div>
        )}

        <form className="border-t border-line p-3" onSubmit={e => { e.preventDefault(); send(input); }}>
          <div className="flex gap-2">
            <label className="sr-only" htmlFor="chat-input">Il tuo messaggio</label>
            <input id="chat-input" value={input} onChange={e => setInput(e.target.value)} disabled={disabled || running} maxLength={2000}
              placeholder="Come ti senti oggi? Scrivi anche RPE o dolori" className="min-w-0 flex-1 rounded-lg border border-line bg-white px-3 py-2" />
            <button type="submit" disabled={disabled || running} className="rounded-lg bg-sea px-4 py-2 font-semibold text-white hover:bg-sea-dark disabled:opacity-50">
              {running ? "Analizzo…" : "Invia"}
            </button>
          </div>
          <label className="mt-2 flex items-center gap-2 text-xs text-mute">Simula un guasto (demo)
            <select value={failure} onChange={e => setFailure(e.target.value)} className="rounded border border-line bg-white px-2 py-1 text-ink">
              <option value="">nessuno</option><option value="wearable">dispositivo/database non risponde</option>
              <option value="knowledge">letteratura non disponibile</option><option value="llm">modello linguistico non disponibile</option>
            </select>
          </label>
        </form>
      </section>
      <ThoughtTrace events={trace} running={running} />
    </div>
  );
}
