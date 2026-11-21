export default function Sparkline({ values, color = "#1D6B80" }: { values: (number | null)[]; color?: string }) {
  const pts = values.map((v, i) => ({ v, i })).filter((p): p is { v: number; i: number } => p.v !== null);
  if (pts.length < 2) return <div className="h-8" />;
  const min = Math.min(...pts.map(p => p.v)), max = Math.max(...pts.map(p => p.v)), span = max - min || 1;
  const w = 120, h = 32, n = values.length - 1 || 1;
  const d = pts.map(p => `${(p.i / n) * w},${h - 3 - ((p.v - min) / span) * (h - 6)}`).join(" ");
  const last = pts[pts.length - 1];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-8 w-full" aria-hidden preserveAspectRatio="none">
      <polyline points={d} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
      <circle cx={(last.i / n) * w} cy={h - 3 - ((last.v - min) / span) * (h - 6)} r="2.5" fill={color} />
    </svg>
  );
}
