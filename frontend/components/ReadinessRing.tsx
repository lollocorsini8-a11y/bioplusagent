"use client";
import { motion, useReducedMotion } from "framer-motion";
import type { Report } from "@/lib/types";
import { LEVEL } from "./level";

const R = 92, C = 2 * Math.PI * R;

export default function ReadinessRing({ report, compact = false }: { report: Report; compact?: boolean }) {
  const reduce = useReducedMotion();
  const meta = LEVEL[report.level];
  const score = report.readiness ?? 0;
  const offset = C * (1 - score / 100);
  return (
    <div className={compact ? "readiness-ring-compact" : "ecg-grid rounded-xl border border-line p-6 sm:p-8"}>
      <div className={compact ? "readiness-ring-layout" : "flex flex-col items-center gap-6 sm:flex-row sm:gap-10"}>
        <div className="relative h-60 w-60 shrink-0" role="img"
          aria-label={`Indice di prontezza ${report.readiness ?? "non disponibile"} su 100, stato ${meta.label}`}>
          <svg viewBox="0 0 220 220" className="h-full w-full -rotate-90">
            <circle cx="110" cy="110" r={R} fill="#FBFCFB" stroke="#D5DFDB" strokeWidth="14" />
            <motion.circle cx="110" cy="110" r={R} fill="none" stroke={meta.color} strokeWidth="14" strokeLinecap="round"
              strokeDasharray={C} initial={{ strokeDashoffset: reduce ? offset : C }} animate={{ strokeDashoffset: offset }}
              transition={{ duration: reduce ? 0 : 1.2, ease: "easeOut" }} key={`${report.as_of}-${score}`} />
          </svg>
          <div className="absolute inset-0 flex flex-col items-center justify-center">
            <span className="tnum font-display text-7xl font-bold leading-none" style={{ color: meta.color }}>
              {report.readiness ?? "–"}
            </span>
            <span className="mt-1 text-sm text-mute">su 100</span>
          </div>
        </div>
        <div className={compact ? "readiness-ring-copy" : "max-w-sm text-center sm:text-left"}>
          <p className="inline-flex items-center gap-2 rounded-full px-3 py-1 text-sm font-semibold" style={{ background: meta.soft, color: meta.color }}>
            <span aria-hidden className="grid h-5 w-5 place-items-center rounded-full text-xs text-white" style={{ background: meta.color }}>{meta.mark}</span>
            {meta.label}
          </p>
          <h2 className="mt-3 font-display text-3xl font-bold leading-tight">Indice di prontezza</h2>
          <p className="mt-2 text-ink/80">{meta.text}</p>
          <p className="mt-3 text-sm text-mute">
            Dati al {report.as_of ?? "–"} · {report.data_days}/28 giorni · affidabilità {report.confidence === "full" ? "piena" : report.confidence === "partial" ? "parziale" : "insufficiente"}
          </p>
          {report.flags.filter(f => f.severity !== "info").length > 0 && (
            <ul className="mt-3 space-y-1 text-sm">
              {report.flags.filter(f => f.severity !== "info").map(f => (
                <li key={f.code} className="flex gap-2"><span aria-hidden>{f.severity === "red" ? "✕" : "!"}</span><span>{f.message}</span></li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}
