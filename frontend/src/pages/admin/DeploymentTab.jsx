import { useState, useEffect } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Rocket, Github, Copy, Check, Download, Server, ShieldCheck, Zap, AlertTriangle, X, Plus, Stethoscope, Wand2, History, Bell } from "lucide-react";

const CAT_ICON = { Calls: Zap, Gateway: Server, Monitoring: Server };

function FileBlock({ file }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(file.content); setCopied(true); setTimeout(() => setCopied(false), 1500); }
    catch (e) { toast.error("Copy failed"); }
  };
  return (
    <div className="mb-3" data-testid={`deploy-file-${file.name}`}>
      <div className="flex items-center justify-between mb-1">
        <span className="font-mono-stitch text-xs font-semibold text-primary-stitch">{file.name}</span>
        <button data-testid={`deploy-copy-${file.name}`} onClick={copy} className="neu-btn rounded-lg px-2.5 py-1 text-xs font-semibold flex items-center gap-1.5 text-primary-stitch">
          {copied ? <><Check className="w-3.5 h-3.5" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
        </button>
      </div>
      <pre className="neu-pressed rounded-2xl p-4 font-mono-stitch text-[12px] leading-relaxed whitespace-pre-wrap break-words max-h-72 overflow-auto" style={{ color: "var(--text)" }}>{file.content}</pre>
    </div>
  );
}

export function DeploymentTab() {
  const [cat, setCat] = useState(null);
  const [domain, setDomain] = useState("");
  const [publicIp, setPublicIp] = useState("");
  const [token, setToken] = useState("");
  const [selected, setSelected] = useState([]);
  const [saving, setSaving] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [applying, setApplying] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [files, setFiles] = useState(null);
  const [paste, setPaste] = useState(null);
  const [activeFile, setActiveFile] = useState(0);
  const [importPreview, setImportPreview] = useState(null);
  const [diag, setDiag] = useState(null);
  const [diagRunning, setDiagRunning] = useState(false);
  const [diagState, setDiagState] = useState({ auto_enabled: false, alerts: [] });

  const loadDiagState = () => api.get("/admin/deploy/diagnose/state").then(({ data }) => setDiagState(data)).catch(() => {});
  useEffect(() => { loadDiagState(); }, []);
  const toggleAuto = async () => {
    const next = !diagState.auto_enabled;
    setDiagState({ ...diagState, auto_enabled: next });
    try { await api.put("/admin/deploy/diagnose/auto", { enabled: next }); toast.success(next ? "Auto re-scan on — admins get alerted when something breaks" : "Auto re-scan off"); }
    catch (e) { toast.error("Couldn't update"); loadDiagState(); }
  };
  const dismissAlerts = async () => {
    try { await api.post("/admin/deploy/diagnose/alerts/seen"); setDiagState({ ...diagState, alerts: [] }); toast.success("Alerts cleared"); }
    catch (e) { toast.error("Couldn't clear"); }
  };
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState([]);
  const toggleHistory = async () => {
    const next = !showHistory; setShowHistory(next);
    if (next) { try { const { data } = await api.get("/admin/deploy/diagnose/history"); setHistory(data.runs); } catch (e) {} }
  };
  const [showChannels, setShowChannels] = useState(false);
  const [channels, setChannels] = useState({ slack_webhook: "", webhook_url: "" });
  useEffect(() => { api.get("/admin/deploy/alert-channels").then(({ data }) => setChannels(data)).catch(() => {}); }, []);
  const saveChannels = async () => {
    try { await api.put("/admin/deploy/alert-channels", channels); toast.success("Alert channels saved"); }
    catch (e) { toast.error("Save failed"); }
  };
  const testChannels = async () => {
    try { const { data } = await api.post("/admin/deploy/alert-channels/test"); const to = Object.entries(data.sent_to).filter(([, v]) => v).map(([k]) => k).join(", "); toast.success(`Test alert dispatched to: ${to}`); }
    catch (e) { toast.error("Test failed"); }
  };

  const runDiagnostics = async () => {
    setDiagRunning(true);
    try {
      const { data } = await api.post("/admin/deploy/diagnose", { autofix: true });
      setDiag(data);
      const f = data.summary.fail, w = data.summary.warn;
      if (f === 0 && w === 0) toast.success("Everything looks healthy!");
      else toast.success(`Scan done — ${data.summary.fail} failing, ${data.summary.warn} need attention`);
    } catch (e) { toast.error("Diagnostics failed"); } finally { setDiagRunning(false); }
  };
  const downloadDiag = async () => {
    try {
      const res = await api.get("/admin/deploy/diagnose/download", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url; a.download = "stitches-diagnostics.md"; document.body.appendChild(a); a.click();
      a.remove(); window.URL.revokeObjectURL(url);
      toast.success("Report downloaded");
    } catch (e) { toast.error("Download failed"); }
  };

  const load = async () => {
    try {
      const { data } = await api.get("/admin/deploy/catalog");
      setCat(data);
      setDomain(data.domain || "");
      setPublicIp(data.public_ip || "");
      setSelected(data.selected || []);
      if (data.secrets_preview) setPaste(data.secrets_preview);
    } catch (e) { toast.error("Could not load deployment catalog"); }
  };
  useEffect(() => { load(); }, []);

  const toggle = (id) => setSelected((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);

  const saveCfg = async () => {
    setSaving(true);
    try {
      await api.put("/admin/deploy/config", { domain, public_ip: publicIp, selected, github_token: token || "" });
      setToken("");
      toast.success("Deployment settings saved");
      load();
    } catch (e) { toast.error("Save failed"); } finally { setSaving(false); }
  };

  const generate = async (regenerate = false) => {
    setGenerating(true);
    try {
      await api.put("/admin/deploy/config", { domain, public_ip: publicIp, selected, github_token: token || "" });
      setToken("");
      const { data } = await api.post("/admin/deploy/generate", { regenerate });
      setFiles(data.files);
      setPaste(data.paste);
      setActiveFile(0);
      toast.success(regenerate ? "Regenerated with fresh secrets" : "Bundle generated");
    } catch (e) { toast.error("Generate failed"); } finally { setGenerating(false); }
  };

  const download = async () => {
    setDownloading(true);
    try {
      const res = await api.get("/admin/deploy/download", { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url; a.download = "stitches-deploy.zip"; document.body.appendChild(a); a.click();
      a.remove(); window.URL.revokeObjectURL(url);
      toast.success("Bundle downloaded");
    } catch (e) { toast.error("Download failed"); } finally { setDownloading(false); }
  };

  const applyCalls = async () => {
    setApplying(true);
    try {
      const { data } = await api.post("/admin/deploy/apply-calls");
      if (data.ok) toast.success("Call credentials applied to Meetings — test connectivity there");
      else toast.error(data.error || "Generate the bundle first");
    } catch (e) { toast.error("Apply failed"); } finally { setApplying(false); }
  };

  const savePreset = async () => {
    const name = window.prompt("Name this preset (e.g. Edge Stack):");
    if (!name || !name.trim()) return;
    try { await api.post("/admin/deploy/presets", { name: name.trim(), selected }); toast.success(`Preset "${name.trim()}" saved`); load(); }
    catch (e) { toast.error(e?.response?.data?.detail || "Could not save preset"); }
  };
  const deletePreset = async (id, e) => {
    e.stopPropagation();
    try { await api.delete(`/admin/deploy/presets/${id}`); toast.success("Preset removed"); load(); }
    catch (e) { toast.error("Could not remove preset"); }
  };
  const exportPreset = async (p, e) => {
    e.stopPropagation();
    try {
      const code = btoa(unescape(encodeURIComponent(JSON.stringify({ name: p.name, ids: p.ids }))));
      await navigator.clipboard.writeText(code);
      toast.success("Preset code copied — share it to import elsewhere");
    } catch (err) { toast.error("Copy failed"); }
  };
  const previewPreset = (name, ids, save) => {
    const clean = ids.filter((i) => cat.catalog.some((c) => c.id === i));
    const adds = clean.filter((i) => !selected.includes(i));
    const removes = selected.filter((i) => !clean.includes(i));
    setImportPreview({ name, ids: clean, adds, removes, save });
  };
  const importPreset = async () => {
    const code = window.prompt("Paste a preset code to import:");
    if (!code || !code.trim()) return;
    try {
      const obj = JSON.parse(decodeURIComponent(escape(atob(code.trim()))));
      if (!obj.name || !Array.isArray(obj.ids)) throw new Error("bad");
      previewPreset(obj.name, obj.ids, true);
    } catch (err) { toast.error("Invalid preset code"); }
  };
  const confirmImport = async () => {
    if (!importPreview) return;
    try {
      if (importPreview.save) {
        await api.post("/admin/deploy/presets", { name: importPreview.name, selected: importPreview.ids });
        toast.success(`Imported "${importPreview.name}"`);
        load();
      } else {
        toast.success(`Applied "${importPreview.name}"`);
      }
      setSelected(importPreview.ids);
      setImportPreview(null);
    } catch (err) { toast.error(err?.response?.data?.detail || "Failed"); }
  };
  const nameOf = (id) => (cat?.catalog.find((c) => c.id === id)?.name) || id;

  if (!cat) return null;
  const cats = [...new Set(cat.catalog.map((c) => c.category))];
  const input = "neu-input rounded-2xl py-3 px-4 text-sm w-full";

  return (
    <div className="space-y-6" data-testid="deployment-tab">
      {importPreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4" data-testid="import-preview-modal">
          <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setImportPreview(null)} />
          <div className="relative neu-raised rounded-[1.75rem] p-6 w-full max-w-md" style={{ background: "var(--surface)" }}>
            <h3 className="font-head font-bold text-xl mb-1" style={{ color: "var(--text)" }}>{importPreview.save ? "Import" : "Apply"} "{importPreview.name}"</h3>
            <p className="text-sm text-muted-stitch mb-4">This preset will change your current selection as follows:</p>
            <div className="space-y-3">
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-green-500 mb-1.5">Adds ({importPreview.adds.length})</p>
                {importPreview.adds.length === 0 ? <p className="text-xs text-muted-stitch">Nothing new.</p> : (
                  <div className="flex flex-wrap gap-2" data-testid="import-adds">
                    {importPreview.adds.map((id) => <span key={id} className="neu-pressed rounded-xl px-3 py-1.5 text-xs font-semibold text-green-500">+ {nameOf(id)}</span>)}
                  </div>
                )}
              </div>
              <div>
                <p className="text-xs font-bold uppercase tracking-wide text-red-400 mb-1.5">Removes ({importPreview.removes.length})</p>
                {importPreview.removes.length === 0 ? <p className="text-xs text-muted-stitch">Nothing removed.</p> : (
                  <div className="flex flex-wrap gap-2" data-testid="import-removes">
                    {importPreview.removes.map((id) => <span key={id} className="neu-pressed rounded-xl px-3 py-1.5 text-xs font-semibold text-red-400">− {nameOf(id)}</span>)}
                  </div>
                )}
              </div>
            </div>
            <div className="flex gap-3 mt-6">
              <button data-testid="import-confirm-btn" onClick={confirmImport} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex-1">{importPreview.save ? "Import & apply" : "Apply preset"}</button>
              <button data-testid="import-cancel-btn" onClick={() => setImportPreview(null)} className="neu-btn rounded-2xl px-5 py-3 font-semibold text-muted-stitch">Cancel</button>
            </div>
          </div>
        </div>
      )}
      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="deploy-diagnose-card">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Stethoscope className="w-5 h-5 text-primary-stitch" /></div>
            <div className="min-w-0">
              <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Why isn't it working?</h3>
              <p className="text-sm text-muted-stitch">Scan the whole app, auto-fix what the System AI safely can, and get a report of anything still needing you.</p>
            </div>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button data-testid="auto-rescan-toggle" onClick={toggleAuto} title="Auto re-scan & alert admins"
              className="neu-btn rounded-2xl px-3 py-3 font-semibold text-xs flex items-center gap-2" style={{ color: diagState.auto_enabled ? "var(--primary)" : "var(--muted)" }}>
              <span className={`w-2 h-2 rounded-full`} style={{ background: diagState.auto_enabled ? "#22c55e" : "var(--neu-dark)" }} />
              Auto {diagState.auto_enabled ? "on" : "off"}
            </button>
            <button data-testid="history-toggle-btn" onClick={toggleHistory} className="neu-btn rounded-2xl px-4 py-3 font-semibold text-primary-stitch flex items-center gap-2"><History className="w-4 h-4" /> History</button>
            <button data-testid="channels-toggle-btn" onClick={() => setShowChannels((v) => !v)} className="neu-btn rounded-2xl px-4 py-3 font-semibold text-primary-stitch flex items-center gap-2"><Bell className="w-4 h-4" /> Channels</button>
            {diag && <button data-testid="diagnose-download-btn" onClick={downloadDiag} className="neu-btn rounded-2xl px-4 py-3 font-semibold text-primary-stitch flex items-center gap-2"><Download className="w-4 h-4" /> Report</button>}
            <button data-testid="run-diagnose-btn" onClick={runDiagnostics} disabled={diagRunning} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2"><Stethoscope className="w-4 h-4" />{diagRunning ? "Scanning…" : "Run diagnostics"}</button>
          </div>
        </div>

        {diagState.alerts?.length > 0 && (
          <div className="neu-pressed rounded-2xl p-4 mt-4 border-l-4" style={{ borderColor: "#ef4444" }} data-testid="diagnose-alerts">
            <div className="flex items-center justify-between gap-3 mb-2">
              <p className="text-sm font-bold text-red-400 flex items-center gap-2"><AlertTriangle className="w-4 h-4" /> {diagState.alerts.length} new issue{diagState.alerts.length > 1 ? "s" : ""} detected since last scan</p>
              <button data-testid="dismiss-alerts-btn" onClick={dismissAlerts} className="neu-btn rounded-lg px-3 py-1.5 text-xs font-semibold text-muted-stitch">Dismiss</button>
            </div>
            <ul className="space-y-1">
              {diagState.alerts.map((a) => (
                <li key={a.alert_id} className="text-xs text-muted-stitch"><span className="font-semibold" style={{ color: "var(--text)" }}>{a.label}</span> — {a.from_status} → <span className="text-red-400 font-semibold">{a.to_status}</span>{a.fix_hint ? ` · ${a.fix_hint}` : ""}</li>
              ))}
            </ul>
          </div>
        )}

        {showChannels && (
          <div className="neu-pressed rounded-2xl p-4 mt-4" data-testid="alert-channels-panel">
            <p className="text-sm font-semibold mb-1 flex items-center gap-2" style={{ color: "var(--text)" }}><Bell className="w-4 h-4 text-primary-stitch" /> Alert channels</p>
            <p className="text-xs text-muted-stitch mb-3">Route health-regression alerts to Slack and/or a webhook, in addition to admin email.</p>
            <div className="space-y-2">
              <input data-testid="slack-webhook-input" value={channels.slack_webhook} onChange={(e) => setChannels({ ...channels, slack_webhook: e.target.value })} placeholder="Slack incoming webhook URL" className="neu-input rounded-2xl py-2.5 px-4 text-sm w-full font-mono-stitch" />
              <input data-testid="webhook-url-input" value={channels.webhook_url} onChange={(e) => setChannels({ ...channels, webhook_url: e.target.value })} placeholder="Generic webhook URL (JSON POST)" className="neu-input rounded-2xl py-2.5 px-4 text-sm w-full font-mono-stitch" />
            </div>
            <div className="flex gap-2 mt-3">
              <button data-testid="save-channels-btn" onClick={saveChannels} className="neu-primary rounded-xl px-4 py-2 text-xs font-semibold">Save channels</button>
              <button data-testid="test-channels-btn" onClick={testChannels} className="neu-btn rounded-xl px-4 py-2 text-xs font-semibold text-primary-stitch">Send test alert</button>
            </div>
          </div>
        )}

        {showHistory && (
          <div className="neu-pressed rounded-2xl p-4 mt-4" data-testid="scan-history-panel">
            <p className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: "var(--text)" }}><History className="w-4 h-4 text-primary-stitch" /> Scan history</p>
            {history.length === 0 ? <p className="text-xs text-muted-stitch">No scans recorded yet.</p> : (
              <div className="space-y-1.5 max-h-64 overflow-y-auto">
                {history.map((r) => (
                  <div key={r.run_id} data-testid="scan-history-row" className="flex items-center justify-between gap-3 text-xs py-1.5 px-2 rounded-lg" style={{ background: "var(--neu-dark)" }}>
                    <span className="text-muted-stitch">{new Date(r.generated_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                    <span className={`font-bold uppercase tracking-wide ${r.trigger === "auto" ? "text-primary-stitch" : "text-muted-stitch"}`}>{r.trigger}</span>
                    <span className="flex items-center gap-2 ml-auto">
                      <span className="text-green-500 font-bold">{r.summary.ok} ok</span>
                      <span className="text-amber-500 font-bold">{r.summary.warn} warn</span>
                      <span className="text-red-400 font-bold">{r.summary.fail} fail</span>
                    </span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {diag && (
          <div className="mt-5" data-testid="diagnose-results">
            <div className="flex gap-2 flex-wrap mb-4">
              <span className="neu-pressed rounded-xl px-3 py-1.5 text-xs font-bold text-green-500">{diag.summary.ok} OK</span>
              <span className="neu-pressed rounded-xl px-3 py-1.5 text-xs font-bold text-amber-500">{diag.summary.warn} warnings</span>
              <span className="neu-pressed rounded-xl px-3 py-1.5 text-xs font-bold text-red-400">{diag.summary.fail} failing</span>
            </div>
            {diag.auto_fixed?.length > 0 && (
              <div className="neu-pressed rounded-2xl p-4 mb-4" data-testid="diagnose-autofixed">
                <p className="text-xs font-bold uppercase tracking-wide text-green-500 mb-1.5 flex items-center gap-1.5"><Wand2 className="w-3.5 h-3.5" /> Auto-fixed by System AI</p>
                <ul className="text-sm text-muted-stitch list-disc pl-5 space-y-0.5">{diag.auto_fixed.map((f, i) => <li key={i}>{f}</li>)}</ul>
              </div>
            )}
            <div className="space-y-2">
              {diag.checks.map((c) => (
                <div key={c.id} data-testid={`diagnose-check-${c.id}`} className="neu-pressed rounded-2xl px-4 py-3 flex items-start gap-3">
                  <span className="text-lg leading-none mt-0.5 shrink-0" style={{ color: c.status === "ok" ? "#22c55e" : c.status === "warn" ? "#f59e0b" : "#ef4444" }}>
                    {c.status === "ok" ? "●" : c.status === "warn" ? "▲" : "✕"}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold flex items-center gap-2" style={{ color: "var(--text)" }}>
                      {c.label}
                      {c.autofixed && <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-green-500" style={{ background: "var(--neu-dark)" }}>AUTO-FIXED</span>}
                      {c.needs_admin && <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-amber-500" style={{ background: "var(--neu-dark)" }}>NEEDS YOU</span>}
                    </p>
                    <p className="text-xs text-muted-stitch mt-0.5">{c.detail}</p>
                    {c.fix_hint && c.status !== "ok" && <p className="text-xs text-primary-stitch mt-1">→ {c.fix_hint}</p>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        <div className="flex items-center gap-3 mb-1">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Rocket className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Deployment Center</h3>
            <p className="text-sm text-muted-stitch">Grab the right open-source repos from GitHub and generate a ready-to-run deploy bundle for your own server.</p>
          </div>
        </div>
        <div className="neu-pressed rounded-2xl p-4 mt-4 flex items-start gap-3">
          <AlertTriangle className="w-5 h-5 mt-0.5 shrink-0 text-amber-500" />
          <p className="text-xs text-muted-stitch">This app runs in a managed pod and can't run Docker itself. It generates artifacts + a one-command installer you run on your VM (with a public IP). Once up, wire the call servers into Stitches with one click below.</p>
        </div>

        <div className="grid sm:grid-cols-2 gap-3 mt-5">
          <div>
            <label className="text-xs font-semibold text-muted-stitch">Domain</label>
            <input data-testid="deploy-domain" value={domain} onChange={(e) => setDomain(e.target.value)} placeholder="toomanystitches.com" className={`${input} mt-1 font-mono-stitch`} />
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-stitch">Server public IP</label>
            <input data-testid="deploy-public-ip" value={publicIp} onChange={(e) => setPublicIp(e.target.value)} placeholder="203.0.113.9" className={`${input} mt-1 font-mono-stitch`} />
          </div>
          <div className="sm:col-span-2">
            <label className="text-xs font-semibold text-muted-stitch flex items-center gap-1.5"><Github className="w-3.5 h-3.5" /> GitHub token (optional — only for private repos / rate limits)</label>
            <input data-testid="deploy-github-token" type="password" value={token} onChange={(e) => setToken(e.target.value)} placeholder={cat.has_github_token ? "•••••• (saved)" : "ghp_… (leave blank — all repos are public)"} className={`${input} mt-1`} />
          </div>
        </div>
      </div>

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="deploy-services-card">
        <h3 className="font-head font-bold text-lg mb-3" style={{ color: "var(--text)" }}>Services to deploy</h3>
        <div className="mb-5">
          <p className="text-xs font-semibold text-muted-stitch mb-2">Quick presets</p>
          <div className="flex gap-2 flex-wrap items-center">
            {[
              { id: "calls", label: "Calls only", ids: ["coturn", "livekit"] },
              { id: "monitoring", label: "Calls + Monitoring", ids: ["coturn", "livekit", "traefik", "prometheus", "grafana", "loki"] },
              { id: "full", label: "Full stack", ids: cat.catalog.map((c) => c.id) },
            ].map((p) => {
              const active = p.ids.length === selected.length && p.ids.every((i) => selected.includes(i));
              return (
                <button key={p.id} data-testid={`deploy-preset-${p.id}`} onClick={() => previewPreset(p.label, p.ids, false)}
                  className={`rounded-2xl px-4 py-2.5 text-sm font-semibold transition-all ${active ? "neu-primary" : "neu-pressed text-primary-stitch"}`}>
                  {p.label}
                </button>
              );
            })}
            {(cat.presets || []).map((p) => {
              const active = p.ids.length === selected.length && p.ids.every((i) => selected.includes(i));
              return (
                <span key={p.id} data-testid={`deploy-custom-preset-${p.id}`} onClick={() => previewPreset(p.name, p.ids, false)}
                  className={`rounded-2xl pl-4 pr-2 py-2.5 text-sm font-semibold transition-all cursor-pointer flex items-center gap-1.5 ${active ? "neu-primary" : "neu-pressed text-primary-stitch"}`}>
                  {p.name}
                  <button data-testid={`deploy-preset-export-${p.id}`} title="Copy shareable code" onClick={(e) => exportPreset(p, e)} className={`rounded-lg p-1 ${active ? "hover:bg-white/20" : "hover:bg-black/10"}`}><Copy className="w-3.5 h-3.5" /></button>
                  <button data-testid={`deploy-preset-delete-${p.id}`} title="Delete preset" onClick={(e) => deletePreset(p.id, e)} className={`rounded-lg p-1 ${active ? "hover:bg-white/20" : "hover:bg-black/10"}`}><X className="w-3.5 h-3.5" /></button>
                </span>
              );
            })}
            <button data-testid="deploy-save-preset-btn" onClick={savePreset} className="rounded-2xl px-4 py-2.5 text-sm font-semibold neu-btn text-muted-stitch flex items-center gap-1.5">
              <Plus className="w-4 h-4" /> Save current as preset
            </button>
            <button data-testid="deploy-import-preset-btn" onClick={importPreset} className="rounded-2xl px-4 py-2.5 text-sm font-semibold neu-btn text-muted-stitch flex items-center gap-1.5">
              <Download className="w-4 h-4" /> Import code
            </button>
          </div>
        </div>
        {cats.map((c) => (
          <div key={c} className="mb-4">
            <p className="text-xs font-bold uppercase tracking-wide text-muted-stitch mb-2">{c}</p>
            <div className="grid sm:grid-cols-2 gap-3">
              {cat.catalog.filter((s) => s.category === c).map((s) => {
                const on = selected.includes(s.id);
                return (
                  <button key={s.id} data-testid={`deploy-svc-${s.id}`} onClick={() => toggle(s.id)}
                    className={`text-left rounded-2xl p-4 transition-all ${on ? "neu-primary" : "neu-pressed"}`}>
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`font-head font-bold ${on ? "text-white" : ""}`} style={on ? {} : { color: "var(--text)" }}>{s.name}</span>
                      {s.required && <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${on ? "bg-white/20 text-white" : "text-primary-stitch"}`} style={on ? {} : { background: "var(--neu-dark)" }}>REQUIRED</span>}
                      {s.provided && <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-amber-500" style={{ background: on ? "rgba(255,255,255,0.15)" : "var(--neu-dark)" }}>ALREADY IN STITCHES</span>}
                    </div>
                    <p className={`text-xs mt-1 ${on ? "text-white/80" : "text-muted-stitch"}`}>{s.description}</p>
                  </button>
                );
              })}
            </div>
          </div>
        ))}
        <div className="flex items-center gap-3 flex-wrap mt-2">
          <button data-testid="deploy-save-btn" onClick={saveCfg} disabled={saving} className="neu-btn rounded-2xl px-6 py-3 font-semibold text-primary-stitch">{saving ? "Saving…" : "Save selection"}</button>
          <button data-testid="deploy-generate-btn" onClick={() => generate(false)} disabled={generating} className="neu-primary rounded-2xl px-6 py-3 font-semibold flex items-center gap-2"><Rocket className="w-4 h-4" />{generating ? "Generating…" : "Generate bundle"}</button>
          {files && <button data-testid="deploy-regenerate-btn" onClick={() => generate(true)} disabled={generating} className="neu-btn rounded-2xl px-5 py-3 font-semibold text-muted-stitch">Regenerate secrets</button>}
        </div>
      </div>

      {files && (
        <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="deploy-output-card">
          <div className="flex items-center justify-between gap-3 flex-wrap mb-4">
            <h3 className="font-head font-bold text-lg" style={{ color: "var(--text)" }}>Generated bundle</h3>
            <button data-testid="deploy-download-btn" onClick={download} disabled={downloading} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2"><Download className="w-4 h-4" />{downloading ? "Preparing…" : "Download .zip"}</button>
          </div>

          {paste && (
            <div className="neu-pressed rounded-2xl p-4 mb-5" data-testid="deploy-paste-card">
              <div className="flex items-center gap-2 mb-2">
                <ShieldCheck className="w-5 h-5 text-green-500" />
                <p className="text-sm font-semibold" style={{ color: "var(--text)" }}>Connect calls to Stitches</p>
              </div>
              <p className="text-xs text-muted-stitch mb-3">After the stack is running on your VM, apply these credentials to Admin → Meetings in one click, or copy them manually.</p>
              <div className="grid sm:grid-cols-2 gap-x-6 gap-y-1 text-xs font-mono-stitch" style={{ color: "var(--text)" }}>
                <span><span className="text-muted-stitch">TURN URLs:</span> {paste.turn_urls}</span>
                <span><span className="text-muted-stitch">LiveKit URL:</span> {paste.livekit_url}</span>
                <span><span className="text-muted-stitch">TURN user:</span> {paste.turn_username}</span>
                <span><span className="text-muted-stitch">LiveKit key:</span> {paste.livekit_api_key}</span>
                <span className="break-all"><span className="text-muted-stitch">TURN cred:</span> {paste.turn_credential}</span>
                <span className="break-all"><span className="text-muted-stitch">LiveKit secret:</span> {paste.livekit_api_secret}</span>
              </div>
              <button data-testid="deploy-apply-calls-btn" onClick={applyCalls} disabled={applying} className="neu-primary rounded-2xl px-5 py-2.5 font-semibold mt-4 flex items-center gap-2"><Zap className="w-4 h-4" />{applying ? "Applying…" : "Apply generated call credentials"}</button>
            </div>
          )}

          <div className="neu-pressed rounded-2xl p-1.5 inline-flex gap-1 mb-4 flex-wrap">
            {files.map((f, i) => (
              <button key={f.name} data-testid={`deploy-tab-${f.name}`} onClick={() => setActiveFile(i)}
                className={`rounded-xl px-3 py-1.5 text-xs font-mono-stitch font-semibold transition-all ${activeFile === i ? "neu-primary" : "text-muted-stitch"}`}>{f.name}</button>
            ))}
          </div>
          <FileBlock file={files[activeFile]} />
        </div>
      )}
    </div>
  );
}
