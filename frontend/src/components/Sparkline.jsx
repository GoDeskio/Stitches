export function Sparkline({ data = [], w = 96, h = 26 }) {
  const arr = data.length ? data : [0];
  const max = Math.max(1, ...arr);
  const n = arr.length;
  const step = n > 1 ? w / (n - 1) : w;
  const pts = arr.map((v, i) => `${(i * step).toFixed(1)},${(h - (v / max) * (h - 5) - 3).toFixed(1)}`).join(" ");
  const total = arr.reduce((a, b) => a + b, 0);
  const last = arr[arr.length - 1] || 0;
  const lastX = (n - 1) * step;
  const lastY = h - (last / max) * (h - 5) - 3;
  return (
    <span className="text-primary-stitch inline-flex" data-testid="bot-sparkline">
      <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="overflow-visible">
        <polyline points={pts} fill="none" stroke="currentColor" strokeWidth="1.5"
          strokeLinejoin="round" strokeLinecap="round" opacity={total ? 1 : 0.3} />
        {total > 0 && <circle cx={lastX} cy={lastY} r="2.4" fill="currentColor" />}
      </svg>
    </span>
  );
}
