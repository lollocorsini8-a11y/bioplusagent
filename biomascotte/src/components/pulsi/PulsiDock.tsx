import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { X } from "lucide-react";
import { Pulsi } from "./Pulsi";
import { PULSI_STATES, type PulsiState } from "./pulsi-states";

export interface PulsiDockProps {
  state: PulsiState;
  /** Override the default speech bubble text */
  message?: string;
  defaultOpen?: boolean;
}

/** Floating bottom-right companion with contextual speech bubble. */
export function PulsiDock({ state, message, defaultOpen = true }: PulsiDockProps) {
  const [open, setOpen] = useState(defaultOpen);
  const text = message ?? PULSI_STATES[state].message;

  return (
    <div className="pointer-events-none fixed right-4 bottom-4 z-50 flex flex-col items-end gap-2 sm:right-6 sm:bottom-6">
      <AnimatePresence>
        {open && (
          <motion.div
            key={state + text}
            initial={{ opacity: 0, y: 10, scale: 0.95 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 6, scale: 0.95 }}
            transition={{ type: "spring", stiffness: 300, damping: 24 }}
            className="pulsi-bubble pointer-events-auto relative max-w-64 rounded-2xl rounded-br-sm px-4 py-3 text-sm"
            role="status"
            aria-live="polite"
          >
            <button
              onClick={() => setOpen(false)}
              aria-label="Chiudi messaggio"
              className="absolute top-1.5 right-1.5 rounded-full p-0.5 text-muted-foreground transition-colors hover:text-foreground"
            >
              <X className="size-3.5" />
            </button>
            <p className="pr-4 leading-snug">{text}</p>
          </motion.div>
        )}
      </AnimatePresence>
      <button
        onClick={() => setOpen((o) => !o)}
        aria-label={open ? "Nascondi Pulsi" : "Parla con Pulsi"}
        className="pointer-events-auto rounded-full transition-transform hover:scale-105 focus-visible:outline-2 focus-visible:outline-ring"
      >
        <Pulsi state={state} size={open ? 110 : 72} />
      </button>
    </div>
  );
}
