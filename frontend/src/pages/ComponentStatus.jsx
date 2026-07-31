import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import axios from "axios";
import { API } from "@/lib/api";
import { ArrowLeft, ShieldOff } from "lucide-react";

const CELL = { ok: "#22c55e", warn: "#f59e0b", fail: "#ef4444" };
const GROUP_META = {
  ok: { color: "#22c55e", label: "Operational" },
  warn: { color: "#f59e0b", label: "Degraded" },
  fail: { color: "#ef4444", label: "Outage" },
};

export default function ComponentStatus() {
  const { key } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    axios.get(`${API}/status/public/component/${key}`)
      .then(({ data }) => setData(data))
      .catch(() => setData({ enabled: false }))
      .finally(() => setLoading(false));
  }, [key]);

  if (loading) {
    return (
      <div className="stitch-wallpaper min-h-screen flex items-center justify-center">
        <div className="stitch-spinner" />
      </div>
    );
  }

  if (!data?.enabled || !data?.label) {
    return (
      <div className="stitch-wallpaper min-h-screen flex items-center justify-center p-6" data-testid="component-unavailable">
        <div className="neu-raised rounded-[1.75rem] p-8 max-w-md text-center" style={{ background: "var(--surface)" }}>
          <div className="neu-sm w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-4"><ShieldOff className="w-6 h-6 text-muted-stitch" /></div>
          <h1 className="font-head font-bold text-2xl mb-2" style={{ color: "var(--text)" }}>Component not available</h1>
          <Link to="/status" className="text-sm text-primary-stitch font-semibold">← Back to status</Link>
        </div>
      </div>
    );
  }

  const gm = GROUP_META[data.status] || GROUP_META.ok;

  return (
    <div className="stitch-wallpaper min-h-screen py-12 px-4" data-testid="component-status-page">
      <div className="max-w-2xl mx-auto space-y-6">
        <Link to="/status" data-testid="component-back" className="inline-flex items-center gap-2 text-sm text-muted-stitch hover:text-primary-stitch transition-colors font-semibold">
          <ArrowLeft className="w-4 h-4" /> {data.title}
        </Link>

        <div className="neu-raised rounded-[1.75rem] p-6 sm:p-8 animate-fade-up flex items-center justify-between gap-4" style={{ borderLeft: `4px solid ${gm.color}` }}>
          <h1 className="font-head font-bold text-2xl sm:text-3xl" style={{ color: "var(--text)" }}>{data.label}</h1>
          <span className="flex items-center gap-2 text-sm font-bold shrink-0" style={{ color: gm.color }}>
            <span className="w-2.5 h-2.5 rounded-full" style={{ background: gm.color }} /> {gm.label}
          </span>
        </div>

        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="component-uptime">
          <div className="grid grid-cols-3 gap-3 mb-6">
            {["24h", "7d", "90d"].map((w) => {
              const pct = data.windows?.[w]?.pct ?? 100;
              return (
                <div key={w} className="neu-pressed rounded-2xl p-4 text-center" data-testid={`component-window-${w}`}>
                  <p className="text-2xl font-head font-bold" style={{ color: pct >= 90 ? "#22c55e" : pct >= 50 ? "#f59e0b" : "#ef4444" }}>{pct}%</p>
                  <p className="text-[11px] text-muted-stitch uppercase tracking-wide mt-1">past {w}</p>
                </div>
              );
            })}
          </div>
          <p className="text-xs font-bold uppercase tracking-wide text-muted-stitch mb-2">Daily uptime (last {data.daily?.length || 0} days)</p>
          <div className="flex items-end gap-1 h-24" data-testid="component-daily-chart">
            {(data.daily || []).map((d, i) => (
              <div key={i} title={`${d.date}: ${d.pct}% (${d.status})`} className="flex-1 rounded-t-sm transition-all hover:opacity-80"
                style={{ height: `${Math.max(6, d.pct)}%`, background: CELL[d.status] || "#22c55e", minWidth: "3px" }} />
            ))}
            {(!data.daily || data.daily.length === 0) && <span className="text-xs text-muted-stitch">No history yet.</span>}
          </div>
        </div>

        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="component-incidents">
          <h2 className="font-head font-bold text-lg mb-4" style={{ color: "var(--text)" }}>Incident history</h2>
          {(data.incidents || []).length === 0 ? (
            <p className="text-sm text-muted-stitch">No incidents recorded for this component. 🎉</p>
          ) : (
            <div className="space-y-3">
              {data.incidents.map((inc, i) => {
                const resolved = inc.status === "resolved";
                return (
                  <div key={i} className="neu-pressed rounded-2xl p-4" data-testid="component-incident-row">
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ color: resolved ? "#22c55e" : "#f59e0b", background: "var(--neu-dark)" }}>{resolved ? "Resolved" : "Investigating"}</span>
                      {inc.impact && <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide" style={{ color: inc.impact === "outage" ? "#ef4444" : "#f59e0b", background: "var(--neu-dark)" }}>{inc.impact}</span>}
                      <span className="text-xs text-muted-stitch ml-auto">{new Date(inc.opened_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                    </div>
                    <div className="space-y-1.5 pl-1">
                      {(inc.updates || []).map((u, j) => (
                        <div key={j} className="flex gap-2 text-sm">
                          <span className="mt-1 w-1.5 h-1.5 rounded-full shrink-0" style={{ background: u.kind === "resolved" ? "#22c55e" : u.kind === "opened" ? "#ef4444" : "var(--primary)" }} />
                          <div>
                            <span className="text-muted-stitch">{u.text}</span>
                            <span className="text-[10px] text-muted-stitch/70 ml-2">{new Date(u.at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <p className="text-center text-xs text-muted-stitch pt-2">Powered by Stitches</p>
      </div>
    </div>
  );
}
