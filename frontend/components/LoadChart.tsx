import type { Report, SeriesPoint } from "@/lib/types";

export default function LoadChart({ series, report }: { series: SeriesPoint[]; report: Report }) {
  const max = Math.max(1, ...series.map(s => s.load));
  const W = 560, H = 140, bw = W / Math.max(series.length, 1);
  const acuteStart = series.length - 7;
  return (
    <figure className="rounded-lg border border-line bg-paper p-4">
      <figcaption className="mb-2 flex flex-wrap items-baseline justify-between gap-2">
        <span className="font-display text-lg font-bold">Carico di allenamento, 28 giorni</span>
        <span className="tnum text-sm text-mute">
          acuto (7 g) {report.acute_load ?? "–"} · cronico (28 g) {report.chronic_load ?? "–"} · ACWR{" "}
          <strong className="text-ink">{report.acwr?.toFixed(2) ?? "–"}</strong>
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H + 18}`} className="w-full" role="img"
        aria-label={`Carico giornaliero degli ultimi ${series.length} giorni. ACWR ${report.acwr?.toFixed(2) ?? "non disponibile"}.`}>
        {acuteStart >= 0 && <rect x={acuteStart * bw} y={0} width={7 * bw} height={H} fill="#E1EEF1" />}
        {series.map((s, i) => {
          const h = (s.load / max) * (H - 8);
          return <rect key={s.day} x={i * bw + 2} y={H - h} width={Math.max(bw - 4, 1)} height={h} rx="2"
            fill={i >= acuteStart ? "#1D6B80" : "#9DB8C0"}><title>{`${s.day}: carico ${Math.round(s.load)}`}</title></rect>;
        })}
        <line x1="0" x2={W} y1={H} y2={H} stroke="#D5DFDB" />
        <text x="2" y={H + 14} fontSize="11" fill="#5B7280">{series[0]?.day.slice(5)}</text>
        <text x={W - 2} y={H + 14} fontSize="11" fill="#5B7280" textAnchor="end">{series[series.length - 1]?.day.slice(5)}</text>
        {acuteStart >= 0 && <text x={acuteStart * bw + 4} y="13" fontSize="11" fill="#14505F">ultimi 7 giorni</text>}
      </svg>
    </figure>
  );
}
