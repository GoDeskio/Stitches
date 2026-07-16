import { useState, useEffect } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Loader } from "@/components/Stitch";
import { StatCard } from "@/pages/admin/StatCard";

export function AutomationTab() {
  const [data, setData] = useState(null);
  const [runs, setRuns] = useState([]);
  const [hasMore, setHasMore] = useState(false);
  const [filter, setFilter] = useState("all"); // all | ok | fail | run | mcp_call
  const [alerts, setAlerts] = useState(null);
  const [savingAlerts, setSavingAlerts] = useState(false);
  const PAGE = 20;

  const fetchPage = (skip, append) => {
    const params = { limit: PAGE, skip };
    if (filter === "ok") params.ok = "true";
    else if (filter === "fail") params.ok = "false";
    else if (filter === "run" || filter === "mcp_call") params.kind = filter;
    return api.get("/admin/integration-runs", { params }).then(({ data }) => {
      setData(data);
      setHasMore(data.has_more);
      setRuns((prev) => (append ? [...prev, ...data.runs] : data.runs));
    }).catch(() => { setData({ total: 0, ok_count: 0, fail_count: 0 }); setRuns([]); setHasMore(false); });
  };
  const load = () => fetchPage(0, false);
  const loadMore = () => fetchPage(runs.length, true);
  useEffect(() => { load(); }, [filter]); // eslint-disable-line
  useEffect(() => { api.get("/admin/automation-alerts").then(({ data }) => setAlerts(data)).catch(() => setAlerts({ enabled: false, threshold: 3, email: "", webhook_url: "" })); }, []);

  const saveAlerts = async () => {
    setSavingAlerts(true);
    try {
      await api.put("/admin/automation-alerts", alerts);
      toast.success(alerts.enabled ? "Failure alerts enabled" : "Alert settings saved");
    } catch (e) { toast.error("Save failed"); } finally { setSavingAlerts(false); }
  };

  if (!data) return <Loader />;
  const FILTERS = [["all", "All"], ["ok", "Succeeded"], ["fail", "Failed"], ["run", "N8N runs"], ["mcp_call", "MCP calls"]];
  return (
    <div className="space-y-6" data-testid="automation-tab">
      <div className="grid grid-cols-3 gap-5">
        <StatCard label="Total runs" value={data.total} />
        <StatCard label="Succeeded" value={data.ok_count} color="#16a34a" />
        <StatCard label="Failed" value={data.fail_count} color="#dc2626" />
      </div>

      {alerts && (
        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="automation-alerts-card">
          <div className="flex items-center justify-between gap-3 mb-1 flex-wrap">
            <div>
              <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Failure alerts</h3>
              <p className="text-sm text-muted-stitch">Get notified when an integration fails repeatedly in a row (in-app, plus optional email & webhook).</p>
            </div>
            <button data-testid="alerts-enabled-toggle" aria-pressed={alerts.enabled} onClick={() => setAlerts({ ...alerts, enabled: !alerts.enabled })}
              className={`w-14 h-8 rounded-full flex items-center px-1 transition-all shrink-0 ${alerts.enabled ? "justify-end" : "justify-start"}`}
              style={{ background: alerts.enabled ? "var(--primary)" : "var(--neu-dark)" }}>
              <span className="w-6 h-6 rounded-full bg-white shadow" />
            </button>
          </div>
          <div className="grid sm:grid-cols-3 gap-3 mt-4">
            <div>
              <label className="text-xs font-semibold text-muted-stitch">Failures in a row</label>
              <input data-testid="alerts-threshold-input" type="number" min="1" max="20" value={alerts.threshold}
                onChange={(e) => setAlerts({ ...alerts, threshold: e.target.value })} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-stitch">Alert email (optional)</label>
              <input data-testid="alerts-email-input" value={alerts.email}
                onChange={(e) => setAlerts({ ...alerts, email: e.target.value })} placeholder="ops@yourco.com" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>
            <div>
              <label className="text-xs font-semibold text-muted-stitch">Webhook URL (optional)</label>
              <input data-testid="alerts-webhook-input" value={alerts.webhook_url}
                onChange={(e) => setAlerts({ ...alerts, webhook_url: e.target.value })} placeholder="https://hooks.slack.com/…" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 font-mono-stitch" />
            </div>
          </div>
          <button data-testid="save-alerts-btn" onClick={saveAlerts} disabled={savingAlerts} className="neu-primary rounded-2xl px-6 py-3 font-semibold mt-4">{savingAlerts ? "Saving…" : "Save alert settings"}</button>
          <p className="text-xs text-muted-stitch mt-3">Email uses the platform SMTP (Admin → Meetings). Webhook receives a JSON POST with the integration name, type and failure count.</p>
        </div>
      )}

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        <div className="flex items-center justify-between gap-3 mb-5 flex-wrap">
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Automation activity</h3>
            <p className="text-sm text-muted-stitch">Every N8N workflow trigger and MCP tool call across the platform.</p>
          </div>
          <button data-testid="automation-refresh" onClick={load} className="neu-btn rounded-xl px-4 py-2 text-sm font-semibold text-primary-stitch">Refresh</button>
        </div>
        <div className="neu-pressed rounded-full p-1.5 flex gap-1 mb-5 overflow-x-auto">
          {FILTERS.map(([id, lbl]) => (
            <button key={id} data-testid={`automation-filter-${id}`} onClick={() => setFilter(id)}
              className={`rounded-full py-2 px-4 text-sm font-semibold whitespace-nowrap ${filter === id ? "neu-primary" : "text-muted-stitch"}`}>{lbl}</button>
          ))}
        </div>
        {runs.length === 0 ? (
          <p className="text-sm text-muted-stitch" data-testid="automation-empty">No automation runs recorded yet.</p>
        ) : (
          <>
            <div className="space-y-3">
              {runs.map((r) => (
                <div key={r.run_id} data-testid="automation-run-row" className="neu-pressed rounded-2xl p-4 flex items-center gap-4">
                  <span className={`w-2.5 h-2.5 rounded-full shrink-0`} style={{ background: r.ok ? "#16a34a" : "#dc2626" }} />
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>
                      {r.integration_name} <span className="text-muted-stitch font-normal">· {r.kind === "mcp_call" ? "MCP tool" : "N8N run"}</span>
                      {r.status_code ? <span className="text-muted-stitch font-normal"> · {r.status_code}</span> : null}
                    </p>
                    <p className="text-xs text-muted-stitch truncate">{r.owner_name} · {new Date(r.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</p>
                  </div>
                  <span className={`text-xs px-3 py-1 rounded-full neu-sm font-semibold ${r.ok ? "text-green-500" : "text-red-500"}`}>{r.ok ? "OK" : "Failed"}</span>
                </div>
              ))}
            </div>
            {hasMore && (
              <button data-testid="automation-load-more" onClick={loadMore} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-primary-stitch mt-5 w-full">Load more</button>
            )}
          </>
        )}
      </div>
    </div>
  );
}

