import Sparkline from "./Sparkline";

export default function MetricCard({ label, value, unit, hint, values, tone = "#1D6B80" }: {
  label: string; value: string; unit?: string; hint?: string; values: (number | null)[]; tone?: string;
}) {
  return (
    <div className="rounded-lg border border-line bg-paper p-4">
      <p className="text-sm text-mute">{label}</p>
      <p className="mt-1 flex items-baseline gap-1">
        <span className="tnum font-display text-3xl font-bold">{value}</span>
        {unit && <span className="text-sm text-mute">{unit}</span>}
      </p>
      <Sparkline values={values} color={tone} />
      {hint && <p className="mt-1 text-xs text-mute">{hint}</p>}
    </div>
  );
}
