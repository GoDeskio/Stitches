export function StatCard({ label, value, color }) {
  return (
    <div className="neu-raised rounded-[1.5rem] p-6 animate-fade-up">
      <p className="font-head font-black text-4xl" style={{ color: color || "var(--text)" }}>{value}</p>
      <p className="text-sm text-muted-stitch mt-1">{label}</p>
    </div>
  );
}


