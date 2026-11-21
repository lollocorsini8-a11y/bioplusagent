import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { Pulsi, PulsiDock, PULSI_STATES, PULSI_STATE_LIST, type PulsiState } from "@/components/pulsi";
import { cn } from "@/lib/utils";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "Pulsi – Mascotte animata BioPulse" },
      { name: "description", content: "Prova dal vivo tutte le espressioni di Pulsi, la mascotte animata del portale BioPulse." },
      { property: "og:title", content: "Pulsi – Mascotte animata BioPulse" },
      { property: "og:description", content: "Prova dal vivo tutte le espressioni di Pulsi, la mascotte animata del portale BioPulse." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: Index,
});

function Index() {
  const [state, setState] = useState<PulsiState>("welcome");
  const cfg = PULSI_STATES[state];

  return (
    <main className="min-h-screen px-6 py-12 font-sans">
      <div className="mx-auto grid max-w-6xl items-center gap-12 lg:grid-cols-2">
        <section className="flex flex-col items-center">
          <Pulsi state={state} size={340} />
          <p className="mt-4 font-mono text-xs tracking-widest text-muted-foreground uppercase">{state}</p>
        </section>

        <section>
          <p className="font-mono text-xs tracking-widest text-primary uppercase">BioPulse Companion</p>
          <h1 className="mt-2 text-5xl font-extrabold tracking-tight">Pulsi</h1>
          <p className="mt-3 max-w-md text-lg text-muted-foreground">{cfg.message}</p>

          <div className="mt-8 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {PULSI_STATE_LIST.map((s) => (
              <button
                key={s}
                onClick={() => setState(s)}
                className={cn(
                  "flex items-center gap-2 rounded-xl border bg-card px-3 py-2 text-left text-sm font-semibold transition-all hover:-translate-y-0.5 hover:shadow-md",
                  s === state && "border-primary ring-2 ring-primary/30",
                )}
              >
                <Pulsi state={s} size={28} trackCursor={false} />
                {PULSI_STATES[s].label}
              </button>
            ))}
          </div>
          <p className="mt-6 text-sm text-muted-foreground">Muovi il mouse: Pulsi ti segue con lo sguardo.</p>
        </section>
      </div>
      <PulsiDock state={state} />
    </main>
  );
}
