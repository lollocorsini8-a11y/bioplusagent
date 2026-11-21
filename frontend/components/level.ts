import type { Level } from "@/lib/types";

export const LEVEL: Record<Level, { label: string; color: string; soft: string; mark: string; text: string }> = {
  green: { label: "Ottimale", color: "#2F7D5B", soft: "#E3F1EA", mark: "✓", text: "Nessun segnale critico rilevato nei dati disponibili; non equivale a un'idoneità all'allenamento." },
  yellow: { label: "Attenzione", color: "#9A6200", soft: "#FBF0D9", mark: "!", text: "Segnale di attenzione: interpretalo nel contesto e chiedi un parere se necessario." },
  red: { label: "Sovraccarico", color: "#B3261E", soft: "#FBE7E5", mark: "✕", text: "Priorità al recupero. Le indicazioni personalizzate sono trattenute; la revisione di un professionista non è garantita." },
  unknown: { label: "Dati insufficienti", color: "#5B7280", soft: "#E8EEEC", mark: "?", text: "Servono più giorni di dati per valutare." },
};
