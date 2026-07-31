import { useEffect, useState } from "react";
import axios from "axios";
import { API } from "@/lib/api";
import { CheckCircle2, AlertTriangle, XCircle, Activity, ShieldOff } from "lucide-react";

const CELL = { ok: "#22c55e", warn: "#f59e0b", fail: "#ef4444" };
const GROUP_META = {
  ok: { color: "#22c55e", label: "Operational" },
  warn: { color: "#f59e0b", label: "Degraded" },
  fail: { color: "#ef4444", label: "Outage" },
};
const OVERALL = {
  operational: { color: "#22c55e", text: "All systems operational", Icon: CheckCircle2 },
  degraded: { color: "#f59e0b", text: "Some systems are degraded", Icon: AlertTriangle },
  outage: { color: "#ef4444", text: "We're experiencing an outage", Icon: XCircle },
};

export default function StatusPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    axios.get(`${API}/status/public`)
      .then(({ data }) => setData(data))
      .catch(() => setData({ enabled: false }))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="stitch-wallpaper min-h-screen flex items-center justify-center">
        <div className="stitch-spinner" />
      </div>
    );
  }

  if (!data?.enabled) {
    return (
      <div className="stitch-wallpaper min-h-screen flex items-center justify-center p-6" data-testid="status-disabled">
        <div className="neu-raised rounded-[1.75rem] p-8 max-w-md text-center" style={{ background: "var(--surface)" }}>
          <div className="neu-sm w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4">
            <ShieldOff className="w-6 h-6 text-muted-stitch" />
          </div>
          <h1 className="font-head font-bold text-2xl mb-2" style={{ color: "var(--text)" }}>Status page not available</h1>
          <p className="text-sm text-muted-stitch">This status page hasn't been published yet. Please check back later.</p>
        </div>
      </div>
    );
  }

  const ov = OVERALL[data.overall] || OVERALL.operational;

  return (
    <div className="stitch-wallpaper min-h-screen py-12 px-4" data-testid="status-page">
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="text-center animate-fade-up">
          <div className="inline-flex items-center gap-2 text-muted-stitch text-xs font-semibold uppercase tracking-widest mb-3">
            <Activity className="w-4 h-4 text-primary-stitch" /> {data.title}
          </div>
        </div>

        <div className="neu-raised rounded-[1.75rem] p-6 sm:p-8 animate-fade-up flex items-center gap-4" data-testid="status-overall"
          style={{ borderLeft: `4px solid ${ov.color}` }}>
          <div className="neu-sm w-14 h-14 rounded-2xl flex items-center justify-center shrink-0">
            <ov.Icon className="w-7 h-7" style={{ color: ov.color }} />
          </div>
          <div>
            <h1 className="font-head font-bold text-2xl sm:text-3xl" style={{ color: "var(--text)" }}>{ov.text}</h1>
            <p className="text-xs text-muted-stitch mt-1">Last checked {new Date(data.generated_at).toLocaleString()}</p>
          </div>
        </div>

        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="status-groups">
          {data.groups.map((g) => {
            const gm = GROUP_META[g.status] || GROUP_META.ok;
            return (
              <div key={g.key} className="py-3.5 border-b last:border-b-0" style={{ borderColor: "var(--neu-dark)" }} data-testid={`status-group-${g.key}`}>
                <div className="flex items-center justify-between gap-3 mb-2">
                  <span className="font-head font-semibold text-sm sm:text-base" style={{ color: "var(--text)" }}>{g.label}</span>
                  <span className="flex items-center gap-2 text-xs font-bold" style={{ color: gm.color }}>
                    <span className="w-2 h-2 rounded-full" style={{ background: gm.color }} /> {gm.label}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex gap-0.5 flex-1">
                    {g.strip.map((s, i) => (
                      <span key={i} className="h-6 flex-1 rounded-sm" style={{ background: CELL[s] || "var(--neu-dark)", minWidth: "3px", maxWidth: "12px" }} />
                    ))}
                  </div>
                  <span className="text-xs font-bold w-14 text-right shrink-0" data-testid={`status-uptime-${g.key}`}
                    style={{ color: g.uptime >= 90 ? "#22c55e" : g.uptime >= 50 ? "#f59e0b" : "#ef4444" }}>{g.uptime}% up</span>
                </div>
              </div>
            );
          })}
        </div>

        {data.incidents?.length > 0 && (
          <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="status-incidents">
            <h2 className="font-head font-bold text-lg mb-4" style={{ color: "var(--text)" }}>Incident history</h2>
            <div className="space-y-3">
              {data.incidents.map((inc, i) => (
                <div key={i} className="neu-pressed rounded-2xl p-4" data-testid="status-incident-row">
                  <div className="flex items-center gap-2 flex-wrap mb-1">
                    <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ color: inc.resolved ? "#22c55e" : "#f59e0b", background: "var(--neu-dark)" }}>
                      {inc.resolved ? "Resolved" : "Investigating"}
                    </span>
                    <span className="font-semibold text-sm" style={{ color: "var(--text)" }}>{inc.label}</span>
                    <span className="text-xs text-muted-stitch ml-auto">{new Date(inc.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                  </div>
                  <p className="text-sm text-muted-stitch">{inc.note}</p>
                </div>
              ))}
            </div>
          </div>
        )}

        <p className="text-center text-xs text-muted-stitch pt-2">Powered by Stitches</p>
      </div>
    </div>
  );
}
