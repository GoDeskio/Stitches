import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { API } from "@/lib/api";
import { CheckCircle2, AlertTriangle, XCircle, Activity, ShieldOff, Bell, Loader2, Wrench, ChevronRight } from "lucide-react";

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
const WIN_LABEL = { "24h": "24 hours", "7d": "7 days", "90d": "90 days" };

function SubscribeBox({ accent }) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState("idle"); // idle | loading | done | error
  const [msg, setMsg] = useState("");
  const submit = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setState("loading");
    try {
      const { data } = await axios.post(`${API}/status/subscribe`, { email: email.trim() });
      setState("done");
      setMsg(data.already ? "You're already subscribed — we'll keep you posted." : "Subscribed! You'll get an email on every incident update.");
    } catch (err) {
      setState("error");
      setMsg(err?.response?.data?.detail || "Couldn't subscribe. Try again.");
    }
  };
  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="status-subscribe">
      <div className="flex items-center gap-3 mb-1">
        <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Bell className="w-5 h-5" style={{ color: accent || "var(--primary)" }} /></div>
        <div>
          <h2 className="font-head font-bold text-lg" style={{ color: "var(--text)" }}>Get status updates</h2>
          <p className="text-sm text-muted-stitch">Subscribe to be emailed the moment we open or resolve an incident.</p>
        </div>
      </div>
      {state === "done" ? (
        <p className="neu-pressed rounded-2xl px-4 py-3 mt-4 text-sm text-green-500 font-semibold" data-testid="subscribe-success">{msg}</p>
      ) : (
        <form onSubmit={submit} className="flex gap-2 mt-4">
          <input data-testid="subscribe-email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="you@company.com" className="neu-input rounded-2xl py-3 px-4 text-sm flex-1" style={{ color: "var(--text)" }} />
          <button data-testid="subscribe-submit" type="submit" disabled={state === "loading"}
            className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2 shrink-0" style={accent ? { background: accent } : undefined}>
            {state === "loading" ? <Loader2 className="w-4 h-4 animate-spin" /> : <Bell className="w-4 h-4" />} Subscribe
          </button>
        </form>
      )}
      {state === "error" && <p className="text-xs text-red-400 mt-2" data-testid="subscribe-error">{msg}</p>}
    </div>
  );
}

export default function StatusPage() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [win, setWin] = useState("90d");

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
  const windows = data.windows || ["24h", "7d", "90d"];
  const activeWin = windows.includes(win) ? win : windows[windows.length - 1];
  const accent = data.accent || "";

  return (
    <div className="stitch-wallpaper min-h-screen py-12 px-4" data-testid="status-page">
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="text-center animate-fade-up">
          {data.logo ? (
            <img data-testid="status-logo" src={data.logo} alt={data.title} className="h-12 mx-auto mb-2 object-contain" />
          ) : null}
          <div className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-widest mb-1" style={{ color: accent || "var(--muted)" }}>
            {!data.logo && <Activity className="w-4 h-4" style={{ color: accent || "var(--primary)" }} />} {data.title}
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

        {data.maintenance?.length > 0 && (
          <div className="space-y-3" data-testid="status-maintenance">
            {data.maintenance.map((m, i) => (
              <div key={i} className="neu-raised rounded-[1.75rem] p-5 animate-fade-up flex items-start gap-3" data-testid="maintenance-banner"
                style={{ borderLeft: "4px solid #3b82f6" }}>
                <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center shrink-0"><Wrench className="w-5 h-5" style={{ color: "#3b82f6" }} /></div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide" style={{ color: "#3b82f6", background: "var(--neu-dark)" }}>{m.state === "in_progress" ? "Maintenance in progress" : "Scheduled maintenance"}</span>
                    <span className="font-head font-bold text-base" style={{ color: "var(--text)" }}>{m.title}</span>
                  </div>
                  {m.message && <p className="text-sm text-muted-stitch mt-1">{m.message}</p>}
                  <p className="text-xs text-muted-stitch mt-1.5">
                    {new Date(m.starts_at).toLocaleString()} → {new Date(m.ends_at).toLocaleString()}
                    {m.components?.length ? ` · ${m.components.join(", ")}` : ""}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}

        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="status-groups">
          <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
            <span className="text-xs font-bold uppercase tracking-wide text-muted-stitch">Uptime over the last {WIN_LABEL[activeWin]}</span>
            <div className="neu-pressed rounded-2xl p-1 inline-flex gap-1" data-testid="uptime-window-tabs">
              {windows.map((w) => (
                <button key={w} data-testid={`window-tab-${w}`} onClick={() => setWin(w)}
                  className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-all ${activeWin === w ? "neu-primary" : "text-muted-stitch"}`}
                  style={activeWin === w && accent ? { background: accent, color: "#fff" } : undefined}>{w}</button>
              ))}
            </div>
          </div>
          {data.groups.map((g) => {
            const gm = GROUP_META[g.status] || GROUP_META.ok;
            const wv = (g.windows && g.windows[activeWin]) || { pct: g.uptime ?? 100, strip: g.strip || [] };
            return (
              <Link key={g.key} to={`/status/${g.key}`} className="block py-3.5 border-b last:border-b-0 group" style={{ borderColor: "var(--neu-dark)" }} data-testid={`status-group-${g.key}`}>
                <div className="flex items-center justify-between gap-3 mb-2">
                  <span className="font-head font-semibold text-sm sm:text-base flex items-center gap-1.5 group-hover:text-primary-stitch transition-colors" style={{ color: "var(--text)" }}>{g.label}<ChevronRight className="w-3.5 h-3.5 text-muted-stitch opacity-0 group-hover:opacity-100 transition-opacity" /></span>
                  <span className="flex items-center gap-2 text-xs font-bold" style={{ color: gm.color }}>
                    <span className="w-2 h-2 rounded-full" style={{ background: gm.color }} /> {gm.label}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <div className="flex gap-0.5 flex-1">
                    {(wv.strip || []).map((s, i) => (
                      <span key={i} className="h-6 flex-1 rounded-sm" style={{ background: CELL[s] || "var(--neu-dark)", minWidth: "3px", maxWidth: "12px" }} />
                    ))}
                    {(!wv.strip || wv.strip.length === 0) && <span className="text-xs text-muted-stitch">No data in this window yet.</span>}
                  </div>
                  <span className="text-xs font-bold w-14 text-right shrink-0" data-testid={`status-uptime-${g.key}`}
                    style={{ color: wv.pct >= 90 ? "#22c55e" : wv.pct >= 50 ? "#f59e0b" : "#ef4444" }}>{wv.pct}% up</span>
                </div>
              </Link>
            );
          })}
        </div>

        <SubscribeBox accent={accent} />

        {data.incidents?.length > 0 && (
          <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="status-incidents">
            <h2 className="font-head font-bold text-lg mb-4" style={{ color: "var(--text)" }}>Incident history</h2>
            <div className="space-y-3">
              {data.incidents.map((inc, i) => {
                const resolved = inc.status === "resolved";
                return (
                  <div key={i} className="neu-pressed rounded-2xl p-4" data-testid="status-incident-row">
                    <div className="flex items-center gap-2 flex-wrap mb-2">
                      <span className="text-xs font-bold px-2 py-0.5 rounded-full" style={{ color: resolved ? "#22c55e" : "#f59e0b", background: "var(--neu-dark)" }}>
                        {resolved ? "Resolved" : "Investigating"}
                      </span>
                      {inc.impact && <span className="text-[10px] font-bold px-2 py-0.5 rounded-full uppercase tracking-wide" style={{ color: inc.impact === "outage" ? "#ef4444" : "#f59e0b", background: "var(--neu-dark)" }}>{inc.impact}</span>}
                      <span className="font-semibold text-sm" style={{ color: "var(--text)" }}>{inc.label}</span>
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
          </div>
        )}

        <p className="text-center text-xs text-muted-stitch pt-2">
          Powered by Stitches · <a data-testid="status-rss-link" href={`${window.location.origin}/api/status/feed.xml`} target="_blank" rel="noreferrer" className="font-semibold hover:underline" style={{ color: accent || "var(--primary)" }}>Subscribe via RSS</a>
        </p>
      </div>
    </div>
  );
}
