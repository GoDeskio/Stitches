import { useState, useEffect } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Rocket, Github, Copy, Check, Download, Server, ShieldCheck, Zap, AlertTriangle, X, Plus, Stethoscope, Wand2, History, Bell, Globe, ExternalLink, NotebookPen } from "lucide-react";

const CAT_ICON = { Calls: Zap, Gateway: Server, Monitoring: Server };

const DIAG_LABEL = {
  mongo: "Database", llm: "AI (LLM)", frontendurl: "Frontend URL", email: "Email",
  turn: "TURN", livekit: "LiveKit", deploysecrets: "Deploy secrets", deploytarget: "Deploy target",
  aimemory: "AI memory", admin: "Admin acct", bots: "Bots", indexes: "DB indexes",
};

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
    try { await api.put("/admin/deploy/diagnose/auto", { enabled: next, cooldown_min: diagState.cooldown_min ?? 60 }); toast.success(next ? "Auto re-scan on — admins get alerted when something breaks" : "Auto re-scan off"); }
    catch (e) { toast.error("Couldn't update"); loadDiagState(); }
  };
  const saveCooldown = async () => {
    try { await api.put("/admin/deploy/diagnose/auto", { enabled: diagState.auto_enabled, cooldown_min: diagState.cooldown_min ?? 60 }); toast.success(`Alert cooldown set to ${diagState.cooldown_min} min`); }
    catch (e) { toast.error("Couldn't save cooldown"); }
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
  const [channels, setChannels] = useState({ slack_webhook: "", webhook_url: "", discord_webhook: "", whatsapp_webhook: "", slack_mode: "all", webhook_mode: "all", discord_mode: "all", whatsapp_mode: "all" });
  useEffect(() => { api.get("/admin/deploy/alert-channels").then(({ data }) => setChannels(data)).catch(() => {}); }, []);
  const saveChannels = async () => {
    try { await api.put("/admin/deploy/alert-channels", channels); toast.success("Alert channels saved"); }
    catch (e) { toast.error("Save failed"); }
  };
  const testChannels = async () => {
    try { const { data } = await api.post("/admin/deploy/alert-channels/test"); const to = Object.entries(data.sent_to).filter(([, v]) => v).map(([k]) => k).join(", "); toast.success(`Test alert dispatched to: ${to}`); }
    catch (e) { toast.error("Test failed"); }
  };

  const [statusPage, setStatusPage] = useState({ enabled: false, title: "Stitches Status" });
  const [savingStatus, setSavingStatus] = useState(false);
  useEffect(() => { api.get("/admin/deploy/status-page").then(({ data }) => setStatusPage(data)).catch(() => {}); }, []);
  const statusUrl = `${window.location.origin}/status`;
  const saveStatusPage = async (patch) => {
    const next = { ...statusPage, ...patch };
    setStatusPage(next); setSavingStatus(true);
    try {
      await api.put("/admin/deploy/status-page", next);
      if (patch.enabled !== undefined) toast.success(next.enabled ? "Status page is now public" : "Status page hidden");
      else toast.success("Status page updated");
    } catch (e) { toast.error("Couldn't save"); } finally { setSavingStatus(false); }
  };
  const copyStatusUrl = async () => {
    try { await navigator.clipboard.writeText(statusUrl); toast.success("Status page link copied"); }
    catch (e) { toast.error("Copy failed"); }
  };
  const refreshStatusMeta = () => api.get("/admin/deploy/status-page").then(({ data }) => setStatusPage(data)).catch(() => {});
  const toggleAutoInc = () => saveStatusPage({ auto_incidents: !statusPage.auto_incidents });
  const badgeUrl = `${window.location.origin}/api/status/badge.svg`;
  const htmlSnippet = `<a href="${statusUrl}" target="_blank" rel="noreferrer"><img src="${badgeUrl}" alt="Stitches status" height="20" /></a>`;
  const mdSnippet = `[![Stitches status](${badgeUrl})](${statusUrl})`;
  const [showEmbed, setShowEmbed] = useState(false);
  const [showDomain, setShowDomain] = useState(false);
  const appHost = window.location.host;
  const copyText = async (t, msg) => { try { await navigator.clipboard.writeText(t); toast.success(msg); } catch (e) { toast.error("Copy failed"); } };
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const uploadLogo = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    setUploadingLogo(true);
    try {
      const { data } = await api.post("/admin/deploy/status-logo", fd, { headers: { "Content-Type": "multipart/form-data" } });
      setStatusPage((sp) => ({ ...sp, logo: data.logo }));
      toast.success("Logo uploaded");
    } catch (err) { toast.error(err?.response?.data?.detail || "Upload failed"); }
    finally { setUploadingLogo(false); e.target.value = ""; }
  };
  const removeLogo = async () => {
    try { await api.delete("/admin/deploy/status-logo"); setStatusPage((sp) => ({ ...sp, logo: "" })); toast.success("Logo removed"); }
    catch (e) { toast.error("Couldn't remove logo"); }
  };

  const [pubIncidents, setPubIncidents] = useState([]);
  const [pubGroups, setPubGroups] = useState([]);
  const [showPubInc, setShowPubInc] = useState(false);
  const [incDrafts, setIncDrafts] = useState({});
  const [newInc, setNewInc] = useState({ group_key: "platform", impact: "degraded", text: "" });
  const loadPubIncidents = async () => {
    try { const { data } = await api.get("/admin/deploy/status-incidents"); setPubIncidents(data.incidents); setPubGroups(data.groups); }
    catch (e) {}
  };
  const togglePubInc = () => { const n = !showPubInc; setShowPubInc(n); if (n) loadPubIncidents(); };
  const postIncUpdate = async (id, resolve) => {
    try {
      await api.post(`/admin/deploy/status-incidents/${id}/update`, { text: incDrafts[id] || "", resolve });
      toast.success(resolve ? "Incident resolved" : "Update posted");
      setIncDrafts({ ...incDrafts, [id]: "" }); loadPubIncidents(); refreshStatusMeta();
    } catch (e) { toast.error("Couldn't post"); }
  };
  const createInc = async () => {
    if (!newInc.text.trim()) { toast.error("Add a short message"); return; }
    try {
      await api.post("/admin/deploy/status-incidents", newInc);
      toast.success("Incident posted — subscribers notified");
      setNewInc({ ...newInc, text: "" }); loadPubIncidents(); refreshStatusMeta();
    } catch (e) { toast.error("Couldn't post incident"); }
  };

  const [showMaint, setShowMaint] = useState(false);
  const [maintList, setMaintList] = useState([]);
  const [maintGroups, setMaintGroups] = useState([]);
  const [newMaint, setNewMaint] = useState({ title: "", message: "", group_keys: [], starts_at: "", ends_at: "", notify_lead_min: 60 });
  const loadMaint = async () => {
    try { const { data } = await api.get("/admin/deploy/maintenance"); setMaintList(data.maintenance); setMaintGroups(data.groups); }
    catch (e) {}
  };
  const toggleMaint = () => { const n = !showMaint; setShowMaint(n); if (n) loadMaint(); };
  const toggleMaintGroup = (k) => setNewMaint((m) => ({ ...m, group_keys: m.group_keys.includes(k) ? m.group_keys.filter((x) => x !== k) : [...m.group_keys, k] }));
  const createMaint = async () => {
    if (!newMaint.starts_at || !newMaint.ends_at) { toast.error("Set a start and end time"); return; }
    try {
      await api.post("/admin/deploy/maintenance", {
        ...newMaint,
        starts_at: new Date(newMaint.starts_at).toISOString(),
        ends_at: new Date(newMaint.ends_at).toISOString(),
      });
      toast.success("Maintenance scheduled — subscribers will be reminded before it starts");
      setNewMaint({ title: "", message: "", group_keys: [], starts_at: "", ends_at: "", notify_lead_min: 60 });
      loadMaint();
    } catch (e) { toast.error(e?.response?.data?.detail || "Couldn't schedule"); }
  };
  const deleteMaint = async (id) => {
    try { await api.delete(`/admin/deploy/maintenance/${id}`); toast.success("Maintenance removed"); loadMaint(); }
    catch (e) { toast.error("Couldn't remove"); }
  };

  const [showIncidents, setShowIncidents] = useState(false);
  const [allAlerts, setAllAlerts] = useState([]);
  const [noteDrafts, setNoteDrafts] = useState({});
  const toggleIncidents = async () => {
    const next = !showIncidents; setShowIncidents(next);
    if (next) {
      try { const { data } = await api.get("/admin/deploy/diagnose/alerts/all"); setAllAlerts(data.alerts); setNoteDrafts(Object.fromEntries(data.alerts.map((a) => [a.alert_id, a.note || ""]))); }
      catch (e) {}
    }
  };
  const saveNote = async (alertId) => {
    try {
      await api.patch(`/admin/deploy/diagnose/alerts/${alertId}/note`, { note: noteDrafts[alertId] || "" });
      setAllAlerts((a) => a.map((x) => (x.alert_id === alertId ? { ...x, note: noteDrafts[alertId] || "" } : x)));
      toast.success("Incident note saved");
    } catch (e) { toast.error("Couldn't save note"); }
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
            <button data-testid="incidents-toggle-btn" onClick={toggleIncidents} className="neu-btn rounded-2xl px-4 py-3 font-semibold text-primary-stitch flex items-center gap-2"><NotebookPen className="w-4 h-4" /> Incidents</button>
            <button data-testid="channels-toggle-btn" onClick={() => setShowChannels((v) => !v)} className="neu-btn rounded-2xl px-4 py-3 font-semibold text-primary-stitch flex items-center gap-2"><Bell className="w-4 h-4" /> Channels</button>
            {diag && <button data-testid="diagnose-download-btn" onClick={downloadDiag} className="neu-btn rounded-2xl px-4 py-3 font-semibold text-primary-stitch flex items-center gap-2"><Download className="w-4 h-4" /> Report</button>}
            <button data-testid="run-diagnose-btn" onClick={runDiagnostics} disabled={diagRunning} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2"><Stethoscope className="w-4 h-4" />{diagRunning ? "Scanning…" : "Run diagnostics"}</button>
          </div>
        </div>

        {diagState.auto_enabled && (
          <div className="neu-pressed rounded-2xl px-4 py-3 mt-4 flex items-center gap-3 flex-wrap" data-testid="alert-cooldown-row">
            <span className="text-sm text-muted-stitch">Re-alert cooldown — don't re-fire the same check for</span>
            <input data-testid="cooldown-input" type="number" min="0" value={diagState.cooldown_min ?? 60}
              onChange={(e) => setDiagState({ ...diagState, cooldown_min: parseInt(e.target.value) || 0 })}
              className="neu-input rounded-xl py-1.5 px-3 text-sm w-20" style={{ color: "var(--text)" }} />
            <span className="text-sm text-muted-stitch">minutes</span>
            <button data-testid="cooldown-save-btn" onClick={saveCooldown} className="neu-btn rounded-xl px-3 py-1.5 text-xs font-semibold text-primary-stitch ml-auto">Save</button>
          </div>
        )}

        {diagState.alerts?.length > 0 && (
          <div className="neu-pressed rounded-2xl p-4 mt-4 border-l-4" style={{ borderColor: "#f59e0b" }} data-testid="diagnose-alerts">
            <div className="flex items-center justify-between gap-3 mb-2">
              <p className="text-sm font-bold flex items-center gap-2" style={{ color: "var(--text)" }}><AlertTriangle className="w-4 h-4 text-amber-500" /> {diagState.alerts.length} health update{diagState.alerts.length > 1 ? "s" : ""} since last scan</p>
              <button data-testid="dismiss-alerts-btn" onClick={dismissAlerts} className="neu-btn rounded-lg px-3 py-1.5 text-xs font-semibold text-muted-stitch">Dismiss</button>
            </div>
            <ul className="space-y-1">
              {diagState.alerts.map((a) => (
                <li key={a.alert_id} className="text-xs" data-testid={`alert-${a.kind || "regression"}`}>
                  {a.kind === "recovery"
                    ? <><span className="text-green-500 font-bold">✓ recovered</span> <span className="font-semibold" style={{ color: "var(--text)" }}>{a.label}</span> <span className="text-muted-stitch">({a.from_status} → ok)</span></>
                    : <><span className="text-red-400 font-bold">▲ broke</span> <span className="font-semibold" style={{ color: "var(--text)" }}>{a.label}</span> <span className="text-muted-stitch">({a.from_status} → {a.to_status})</span>{a.fix_hint ? <span className="text-muted-stitch"> · {a.fix_hint}</span> : ""}</>}
                </li>
              ))}
            </ul>
          </div>
        )}

        {showChannels && (
          <div className="neu-pressed rounded-2xl p-4 mt-4" data-testid="alert-channels-panel">
            <p className="text-sm font-semibold mb-1 flex items-center gap-2" style={{ color: "var(--text)" }}><Bell className="w-4 h-4 text-primary-stitch" /> Alert channels</p>
            <p className="text-xs text-muted-stitch mb-3">Route health-regression alerts, incident events and maintenance heads-ups to Slack, Discord, WhatsApp and/or a webhook, in addition to admin email. Pick which events each channel receives to cut noise.</p>
            <div className="space-y-2">
              {[
                { key: "slack_webhook", modeKey: "slack_mode", testid: "slack", ph: "Slack incoming webhook URL" },
                { key: "discord_webhook", modeKey: "discord_mode", testid: "discord", ph: "Discord webhook URL" },
                { key: "whatsapp_webhook", modeKey: "whatsapp_mode", testid: "whatsapp", ph: "WhatsApp webhook URL (Twilio / Zapier / gateway)" },
                { key: "webhook_url", modeKey: "webhook_mode", testid: "webhook-url", ph: "Generic webhook URL (JSON POST)" },
              ].map((c) => (
                <div key={c.key} className="flex gap-2">
                  <input data-testid={`${c.testid}-webhook-input`} value={channels[c.key] || ""} onChange={(e) => setChannels({ ...channels, [c.key]: e.target.value })} placeholder={c.ph} className="neu-input rounded-2xl py-2.5 px-4 text-sm flex-1 font-mono-stitch" />
                  <select data-testid={`${c.testid}-mode-select`} value={channels[c.modeKey] || "all"} onChange={(e) => setChannels({ ...channels, [c.modeKey]: e.target.value })} className="neu-input rounded-2xl py-2.5 px-3 text-xs w-36 shrink-0" style={{ color: "var(--text)" }}>
                    <option value="all">All events</option>
                    <option value="incidents">Incidents</option>
                    <option value="outages">Outages only</option>
                    <option value="maintenance">Maintenance only</option>
                  </select>
                </div>
              ))}
            </div>
            <p className="text-[11px] text-muted-stitch mt-2">WhatsApp has no native incoming webhook — point this at a Twilio Function, Zapier/Make "Catch Hook", or your own WhatsApp gateway that forwards the JSON <span className="font-mono-stitch">{`{message}`}</span> to WhatsApp.</p>
            <div className="flex gap-2 mt-3">
              <button data-testid="save-channels-btn" onClick={saveChannels} className="neu-primary rounded-xl px-4 py-2 text-xs font-semibold">Save channels</button>
              <button data-testid="test-channels-btn" onClick={testChannels} className="neu-btn rounded-xl px-4 py-2 text-xs font-semibold text-primary-stitch">Send test alert</button>
            </div>
          </div>
        )}

        {showIncidents && (
          <div className="neu-pressed rounded-2xl p-4 mt-4" data-testid="incident-log-panel">
            <p className="text-sm font-semibold mb-1 flex items-center gap-2" style={{ color: "var(--text)" }}><NotebookPen className="w-4 h-4 text-primary-stitch" /> Incident log</p>
            <p className="text-xs text-muted-stitch mb-3">Annotate any health alert with a short note (e.g. "fixed by rotating the Mailgun key"). Notes with text also appear on your public status page.</p>
            {allAlerts.length === 0 ? <p className="text-xs text-muted-stitch">No health alerts recorded yet.</p> : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {allAlerts.map((a) => (
                  <div key={a.alert_id} data-testid="incident-row" className="rounded-xl p-3" style={{ background: "var(--neu-dark)" }}>
                    <div className="flex items-center gap-2 flex-wrap text-xs">
                      {a.kind === "recovery"
                        ? <span className="text-green-500 font-bold">✓ recovered</span>
                        : <span className="text-red-400 font-bold">▲ broke</span>}
                      <span className="font-semibold" style={{ color: "var(--text)" }}>{a.label}</span>
                      <span className="text-muted-stitch">({a.from_status} → {a.to_status})</span>
                      <span className="text-muted-stitch ml-auto">{new Date(a.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                    </div>
                    <div className="flex gap-2 mt-2">
                      <input data-testid={`incident-note-input-${a.alert_id}`} value={noteDrafts[a.alert_id] ?? ""} onChange={(e) => setNoteDrafts({ ...noteDrafts, [a.alert_id]: e.target.value })} placeholder="Add an incident note…" className="neu-input rounded-xl py-2 px-3 text-xs flex-1" style={{ color: "var(--text)" }} />
                      <button data-testid={`incident-note-save-${a.alert_id}`} onClick={() => saveNote(a.alert_id)} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-primary-stitch">Save</button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {showHistory && (
          <div className="neu-pressed rounded-2xl p-4 mt-4" data-testid="scan-history-panel">            <p className="text-sm font-semibold mb-3 flex items-center gap-2" style={{ color: "var(--text)" }}><History className="w-4 h-4 text-primary-stitch" /> Scan history</p>
            {history.length === 0 ? <p className="text-xs text-muted-stitch">No scans recorded yet.</p> : (
              <>
                <div className="mb-4" data-testid="uptime-chart">
                  <p className="text-[11px] font-bold uppercase tracking-wide text-muted-stitch mb-2">Per-subsystem uptime (oldest → newest)</p>
                  {(() => {
                    const runs = [...history].reverse();
                    const ids = [...new Set(history.flatMap((r) => Object.keys(r.statuses || {})))];
                    const color = (s) => s === "ok" ? "#22c55e" : s === "warn" ? "#f59e0b" : s === "fail" ? "#ef4444" : "var(--neu-dark)";
                    return ids.map((id) => {
                      const seen = history.filter((r) => (r.statuses || {})[id]);
                      const okc = seen.filter((r) => r.statuses[id] === "ok").length;
                      const pct = seen.length ? Math.round(okc / seen.length * 100) : 100;
                      return (
                      <div key={id} data-testid={`uptime-row-${id}`} className="flex items-center gap-2 mb-1">
                        <span className="text-[11px] w-24 shrink-0 truncate" style={{ color: "var(--text)" }}>{DIAG_LABEL[id] || id}</span>
                        <div className="flex gap-0.5 flex-1">
                          {runs.map((r) => (
                            <span key={r.run_id} title={`${DIAG_LABEL[id] || id}: ${(r.statuses || {})[id] || "n/a"} · ${new Date(r.generated_at).toLocaleString()}`}
                              className="h-4 flex-1 rounded-sm" style={{ background: color((r.statuses || {})[id]), minWidth: "6px", maxWidth: "20px" }} />
                          ))}
                        </div>
                        <span data-testid={`uptime-pct-${id}`} className="text-[11px] font-bold w-10 text-right shrink-0" style={{ color: pct >= 90 ? "#22c55e" : pct >= 50 ? "#f59e0b" : "#ef4444" }}>{pct}%</span>
                      </div>
                      );
                    });
                  })()}
                  <div className="flex items-center gap-3 mt-2 text-[10px] text-muted-stitch">
                    <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: "#22c55e" }} /> OK</span>
                    <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: "#f59e0b" }} /> Warn</span>
                    <span className="flex items-center gap-1"><span className="w-2.5 h-2.5 rounded-sm" style={{ background: "#ef4444" }} /> Fail</span>
                  </div>
                </div>
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
              </>
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

      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="status-page-card">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3 min-w-0">
            <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Globe className="w-5 h-5 text-primary-stitch" /></div>
            <div className="min-w-0">
              <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Public status page</h3>
              <p className="text-sm text-muted-stitch">Turn your subsystem uptime strips into a shareable "all systems operational" page anyone can view — no login required.</p>
            </div>
          </div>
          <button data-testid="status-page-toggle" onClick={() => saveStatusPage({ enabled: !statusPage.enabled })} disabled={savingStatus}
            className="neu-btn rounded-2xl px-4 py-3 font-semibold text-xs flex items-center gap-2 shrink-0" style={{ color: statusPage.enabled ? "var(--primary)" : "var(--muted)" }}>
            <span className="w-2 h-2 rounded-full" style={{ background: statusPage.enabled ? "#22c55e" : "var(--neu-dark)" }} />
            {statusPage.enabled ? "Public — live" : "Private — hidden"}
          </button>
        </div>
        <div className="grid sm:grid-cols-[1fr_auto] gap-3 items-end mt-4">
          <div>
            <label className="text-xs font-semibold text-muted-stitch">Status page title</label>
            <input data-testid="status-page-title" value={statusPage.title} onChange={(e) => setStatusPage({ ...statusPage, title: e.target.value })} onBlur={() => saveStatusPage({})} placeholder="Stitches Status" className={`${input} mt-1`} />
          </div>
          <div className="flex gap-2">
            <button data-testid="status-page-copy" onClick={copyStatusUrl} className="neu-btn rounded-2xl px-4 py-3 font-semibold text-primary-stitch flex items-center gap-2"><Copy className="w-4 h-4" /> Copy link</button>
            <a data-testid="status-page-open" href={statusUrl} target="_blank" rel="noreferrer" className="neu-primary rounded-2xl px-4 py-3 font-semibold flex items-center gap-2"><ExternalLink className="w-4 h-4" /> View</a>
          </div>
        </div>
        {!statusPage.enabled && <p className="text-xs text-amber-500 mt-3">Turn this on to make <span className="font-mono-stitch break-all">{statusUrl}</span> viewable by anyone.</p>}

        <div className="neu-pressed rounded-2xl p-4 mt-4" data-testid="status-theme-row">
          <p className="text-sm font-semibold mb-1" style={{ color: "var(--text)" }}>Brand your status page</p>
          <p className="text-xs text-muted-stitch mb-3">Set an accent color and logo so the public page matches your brand.</p>
          <div className="flex items-end gap-4 flex-wrap">
            <div>
              <label className="text-[11px] text-muted-stitch">Accent color</label>
              <div className="flex items-center gap-2 mt-1">
                <input data-testid="theme-accent-color" type="color" value={statusPage.accent || "#a11a2b"} onChange={(e) => setStatusPage({ ...statusPage, accent: e.target.value })} className="w-10 h-10 rounded-xl border-0 bg-transparent cursor-pointer" />
                <input data-testid="theme-accent-hex" value={statusPage.accent || ""} onChange={(e) => setStatusPage({ ...statusPage, accent: e.target.value })} placeholder="#a11a2b" className="neu-input rounded-xl py-2 px-3 text-sm w-28 font-mono-stitch" style={{ color: "var(--text)" }} />
                <button data-testid="theme-accent-apply" onClick={() => saveStatusPage({})} className="neu-primary rounded-xl px-4 py-2 text-xs font-semibold">Apply</button>
                {statusPage.accent && <button data-testid="theme-accent-clear" onClick={() => saveStatusPage({ accent: "" })} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-muted-stitch">Clear</button>}
              </div>
            </div>
            <div>
              <label className="text-[11px] text-muted-stitch">Logo</label>
              <div className="flex items-center gap-2 mt-1">
                {statusPage.logo && <img data-testid="theme-logo-preview" src={statusPage.logo} alt="logo" className="h-9 object-contain neu-pressed rounded-lg px-2 py-1" />}
                <label data-testid="theme-logo-upload" className="neu-btn rounded-xl px-4 py-2 text-xs font-semibold text-primary-stitch cursor-pointer">
                  {uploadingLogo ? "Uploading…" : statusPage.logo ? "Replace" : "Upload logo"}
                  <input type="file" accept="image/*" onChange={uploadLogo} className="hidden" />
                </label>
                {statusPage.logo && <button data-testid="theme-logo-remove" onClick={removeLogo} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-muted-stitch">Remove</button>}
              </div>
            </div>
          </div>
        </div>

        <div className="neu-pressed rounded-2xl p-4 mt-4 flex items-center justify-between gap-3 flex-wrap" data-testid="auto-incident-row">
          <div className="min-w-0">
            <p className="text-sm font-semibold" style={{ color: "var(--text)" }}>Auto-post incidents</p>
            <p className="text-xs text-muted-stitch">When a subsystem breaks, automatically open a public incident and mark it resolved once it recovers. Subscribers are emailed on every change.</p>
          </div>
          <button data-testid="auto-incident-toggle" onClick={toggleAutoInc} disabled={savingStatus}
            className="neu-btn rounded-2xl px-4 py-2.5 font-semibold text-xs flex items-center gap-2 shrink-0" style={{ color: statusPage.auto_incidents ? "var(--primary)" : "var(--muted)" }}>
            <span className="w-2 h-2 rounded-full" style={{ background: statusPage.auto_incidents ? "#22c55e" : "var(--neu-dark)" }} />
            {statusPage.auto_incidents ? "Auto on" : "Auto off"}
          </button>
        </div>

        <div className="flex items-center gap-3 mt-4 flex-wrap">
          <span data-testid="subscriber-count" className="neu-pressed rounded-xl px-3 py-1.5 text-xs font-semibold text-primary-stitch">{statusPage.subscribers ?? 0} subscriber{(statusPage.subscribers ?? 0) === 1 ? "" : "s"}</span>
          <span data-testid="open-incident-count" className="neu-pressed rounded-xl px-3 py-1.5 text-xs font-semibold" style={{ color: (statusPage.open_incidents ?? 0) > 0 ? "#f59e0b" : "var(--muted)" }}>{statusPage.open_incidents ?? 0} open incident{(statusPage.open_incidents ?? 0) === 1 ? "" : "s"}</span>
          <div className="flex gap-2 ml-auto">
            <button data-testid="manage-incidents-btn" onClick={togglePubInc} className="neu-btn rounded-xl px-4 py-1.5 text-xs font-semibold text-primary-stitch">{showPubInc ? "Hide incidents" : "Manage incidents"}</button>
            <button data-testid="manage-maintenance-btn" onClick={toggleMaint} className="neu-btn rounded-xl px-4 py-1.5 text-xs font-semibold text-primary-stitch">{showMaint ? "Hide maintenance" : "Schedule maintenance"}</button>
            <button data-testid="embed-toggle-btn" onClick={() => setShowEmbed((v) => !v)} className="neu-btn rounded-xl px-4 py-1.5 text-xs font-semibold text-primary-stitch">{showEmbed ? "Hide embed" : "Embed badge"}</button>
            <button data-testid="domain-toggle-btn" onClick={() => setShowDomain((v) => !v)} className="neu-btn rounded-xl px-4 py-1.5 text-xs font-semibold text-primary-stitch">{showDomain ? "Hide domain" : "Custom domain"}</button>
          </div>
        </div>

        {showPubInc && (
          <div className="neu-pressed rounded-2xl p-4 mt-3" data-testid="manage-incidents-panel">
            <p className="text-xs font-bold uppercase tracking-wide text-muted-stitch mb-2">Post a new incident</p>
            <div className="grid sm:grid-cols-[1fr_1fr] gap-2 mb-2">
              <select data-testid="new-incident-group" value={newInc.group_key} onChange={(e) => setNewInc({ ...newInc, group_key: e.target.value })} className="neu-input rounded-xl py-2 px-3 text-sm" style={{ color: "var(--text)" }}>
                {(pubGroups.length ? pubGroups : [{ key: "platform", label: "Platform" }]).map((g) => <option key={g.key} value={g.key}>{g.label}</option>)}
              </select>
              <select data-testid="new-incident-impact" value={newInc.impact} onChange={(e) => setNewInc({ ...newInc, impact: e.target.value })} className="neu-input rounded-xl py-2 px-3 text-sm" style={{ color: "var(--text)" }}>
                <option value="degraded">Degraded</option>
                <option value="outage">Outage</option>
              </select>
            </div>
            <div className="flex gap-2">
              <input data-testid="new-incident-text" value={newInc.text} onChange={(e) => setNewInc({ ...newInc, text: e.target.value })} placeholder="What's happening? (shown publicly)" className="neu-input rounded-xl py-2 px-3 text-sm flex-1" style={{ color: "var(--text)" }} />
              <button data-testid="new-incident-post" onClick={createInc} className="neu-primary rounded-xl px-4 py-2 text-xs font-semibold shrink-0">Post</button>
            </div>

            <p className="text-xs font-bold uppercase tracking-wide text-muted-stitch mt-4 mb-2">Incidents</p>
            {pubIncidents.length === 0 ? <p className="text-xs text-muted-stitch">No incidents yet — auto-post will create them when something breaks.</p> : (
              <div className="space-y-2 max-h-80 overflow-y-auto">
                {pubIncidents.map((inc) => (
                  <div key={inc.incident_id} data-testid="pub-incident-row" className="rounded-xl p-3" style={{ background: "var(--neu-dark)" }}>
                    <div className="flex items-center gap-2 flex-wrap text-xs mb-1">
                      <span className="font-bold px-2 py-0.5 rounded-full" style={{ color: inc.status === "resolved" ? "#22c55e" : "#f59e0b", background: "var(--surface)" }}>{inc.status === "resolved" ? "Resolved" : "Investigating"}</span>
                      {inc.auto && <span className="text-[10px] font-bold px-2 py-0.5 rounded-full text-primary-stitch" style={{ background: "var(--surface)" }}>AUTO</span>}
                      <span className="font-semibold" style={{ color: "var(--text)" }}>{inc.group_label}</span>
                      <span className="text-muted-stitch ml-auto">{new Date(inc.opened_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span>
                    </div>
                    <p className="text-xs text-muted-stitch mb-2">{(inc.updates || []).slice(-1)[0]?.text}</p>
                    {inc.status !== "resolved" && (
                      <div className="flex gap-2">
                        <input data-testid={`incident-update-input-${inc.incident_id}`} value={incDrafts[inc.incident_id] ?? ""} onChange={(e) => setIncDrafts({ ...incDrafts, [inc.incident_id]: e.target.value })} placeholder="Post an update…" className="neu-input rounded-lg py-1.5 px-3 text-xs flex-1" style={{ color: "var(--text)" }} />
                        <button data-testid={`incident-update-btn-${inc.incident_id}`} onClick={() => postIncUpdate(inc.incident_id, false)} className="neu-btn rounded-lg px-3 py-1.5 text-xs font-semibold text-primary-stitch">Update</button>
                        <button data-testid={`incident-resolve-btn-${inc.incident_id}`} onClick={() => postIncUpdate(inc.incident_id, true)} className="neu-btn rounded-lg px-3 py-1.5 text-xs font-semibold text-green-500">Resolve</button>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
        {showMaint && (
          <div className="neu-pressed rounded-2xl p-4 mt-3" data-testid="manage-maintenance-panel">
            <p className="text-xs font-bold uppercase tracking-wide text-muted-stitch mb-2">Schedule a maintenance window</p>
            <input data-testid="maint-title" value={newMaint.title} onChange={(e) => setNewMaint({ ...newMaint, title: e.target.value })} placeholder="Title (e.g. Database upgrade)" className="neu-input rounded-xl py-2 px-3 text-sm w-full mb-2" style={{ color: "var(--text)" }} />
            <input data-testid="maint-message" value={newMaint.message} onChange={(e) => setNewMaint({ ...newMaint, message: e.target.value })} placeholder="What to expect (shown publicly)" className="neu-input rounded-xl py-2 px-3 text-sm w-full mb-2" style={{ color: "var(--text)" }} />
            <div className="grid sm:grid-cols-2 gap-2 mb-2">
              <div><label className="text-[11px] text-muted-stitch">Starts</label><input data-testid="maint-start" type="datetime-local" value={newMaint.starts_at} onChange={(e) => setNewMaint({ ...newMaint, starts_at: e.target.value })} className="neu-input rounded-xl py-2 px-3 text-sm w-full" style={{ color: "var(--text)" }} /></div>
              <div><label className="text-[11px] text-muted-stitch">Ends</label><input data-testid="maint-end" type="datetime-local" value={newMaint.ends_at} onChange={(e) => setNewMaint({ ...newMaint, ends_at: e.target.value })} className="neu-input rounded-xl py-2 px-3 text-sm w-full" style={{ color: "var(--text)" }} /></div>
            </div>
            <div className="mb-2">
              <label className="text-[11px] text-muted-stitch">Affected components</label>
              <div className="flex gap-2 flex-wrap mt-1">
                {maintGroups.map((g) => (
                  <button key={g.key} data-testid={`maint-group-${g.key}`} onClick={() => toggleMaintGroup(g.key)} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${newMaint.group_keys.includes(g.key) ? "neu-primary" : "neu-pressed text-primary-stitch"}`}>{g.label}</button>
                ))}
              </div>
            </div>
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <label className="text-[11px] text-muted-stitch">Email subscribers</label>
              <input data-testid="maint-lead" type="number" min="0" value={newMaint.notify_lead_min} onChange={(e) => setNewMaint({ ...newMaint, notify_lead_min: parseInt(e.target.value) || 0 })} className="neu-input rounded-lg py-1.5 px-2 text-xs w-20" style={{ color: "var(--text)" }} />
              <span className="text-[11px] text-muted-stitch">minutes before it starts</span>
              <button data-testid="maint-schedule-btn" onClick={createMaint} className="neu-primary rounded-xl px-4 py-2 text-xs font-semibold ml-auto">Schedule</button>
            </div>
            {maintList.length === 0 ? <p className="text-xs text-muted-stitch">No maintenance windows scheduled.</p> : (
              <div className="space-y-2 max-h-64 overflow-y-auto">
                {maintList.map((m) => (
                  <div key={m.maint_id} data-testid="maint-row" className="rounded-xl p-3 flex items-start gap-2" style={{ background: "var(--neu-dark)" }}>
                    <div className="min-w-0 flex-1">
                      <div className="flex items-center gap-2 flex-wrap text-xs">
                        <span className="font-bold px-2 py-0.5 rounded-full" style={{ color: m.state === "in_progress" ? "#3b82f6" : m.state === "completed" ? "var(--muted)" : "#22c55e", background: "var(--surface)" }}>{m.state}</span>
                        <span className="font-semibold" style={{ color: "var(--text)" }}>{m.title}</span>
                      </div>
                      <p className="text-[11px] text-muted-stitch mt-1">{new Date(m.starts_at).toLocaleString()} → {new Date(m.ends_at).toLocaleString()}</p>
                    </div>
                    <button data-testid={`maint-delete-${m.maint_id}`} onClick={() => deleteMaint(m.maint_id)} className="neu-btn rounded-lg p-1.5 text-muted-stitch shrink-0"><X className="w-3.5 h-3.5" /></button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {showEmbed && (
          <div className="neu-pressed rounded-2xl p-4 mt-3" data-testid="embed-panel">
            <p className="text-xs font-bold uppercase tracking-wide text-muted-stitch mb-2">Status badge</p>
            <p className="text-xs text-muted-stitch mb-3">Drop this live badge on your marketing site, docs or README. It auto-updates and links back to your status page.</p>
            <div className="flex items-center gap-3 mb-3">
              <img data-testid="embed-badge-preview" src={badgeUrl} alt="status badge" className="h-5" />
              <span className="text-[11px] text-muted-stitch">live preview</span>
            </div>
            <label className="text-[11px] text-muted-stitch">HTML</label>
            <div className="flex gap-2 mb-2">
              <code data-testid="embed-html" className="neu-input rounded-xl py-2 px-3 text-[11px] font-mono-stitch flex-1 overflow-x-auto whitespace-nowrap" style={{ color: "var(--text)" }}>{htmlSnippet}</code>
              <button data-testid="embed-html-copy" onClick={() => copyText(htmlSnippet, "HTML snippet copied")} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-primary-stitch shrink-0"><Copy className="w-3.5 h-3.5" /></button>
            </div>
            <label className="text-[11px] text-muted-stitch">Markdown</label>
            <div className="flex gap-2">
              <code data-testid="embed-md" className="neu-input rounded-xl py-2 px-3 text-[11px] font-mono-stitch flex-1 overflow-x-auto whitespace-nowrap" style={{ color: "var(--text)" }}>{mdSnippet}</code>
              <button data-testid="embed-md-copy" onClick={() => copyText(mdSnippet, "Markdown snippet copied")} className="neu-btn rounded-xl px-3 py-2 text-xs font-semibold text-primary-stitch shrink-0"><Copy className="w-3.5 h-3.5" /></button>
            </div>
            {!statusPage.enabled && <p className="text-xs text-amber-500 mt-3">The badge shows "unknown" until you make the status page public.</p>}
          </div>
        )}

        {showDomain && (
          <div className="neu-pressed rounded-2xl p-4 mt-3" data-testid="domain-panel">
            <p className="text-sm font-semibold mb-1 flex items-center gap-2" style={{ color: "var(--text)" }}><Globe className="w-4 h-4 text-primary-stitch" /> Put the status page on your own domain</p>
            <p className="text-xs text-muted-stitch mb-3">Host it at <span className="font-mono-stitch">status.yourdomain.com</span> so it feels like part of your brand. Two-minute DNS setup:</p>
            <ol className="space-y-3 text-sm" style={{ color: "var(--text)" }}>
              <li className="flex gap-3">
                <span className="neu-sm w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-primary-stitch shrink-0">1</span>
                <div className="min-w-0">
                  <p>In your DNS provider, add a <strong>CNAME</strong> record:</p>
                  <div className="neu-input rounded-xl py-2 px-3 mt-1 text-[11px] font-mono-stitch overflow-x-auto whitespace-nowrap" style={{ color: "var(--text)" }} data-testid="domain-cname">status &nbsp;→&nbsp; {appHost}</div>
                  <button data-testid="domain-cname-copy" onClick={() => copyText(appHost, "Target host copied")} className="neu-btn rounded-lg px-3 py-1.5 mt-2 text-xs font-semibold text-primary-stitch flex items-center gap-2"><Copy className="w-3.5 h-3.5" /> Copy target host</button>
                </div>
              </li>
              <li className="flex gap-3">
                <span className="neu-sm w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-primary-stitch shrink-0">2</span>
                <p className="min-w-0">Wait for DNS to propagate (usually a few minutes). TLS is handled automatically for the mapped host.</p>
              </li>
              <li className="flex gap-3">
                <span className="neu-sm w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-primary-stitch shrink-0">3</span>
                <p className="min-w-0">Visit <span className="font-mono-stitch">https://status.yourdomain.com/status</span> — your branded status page, live on your own domain.</p>
              </li>
            </ol>
            <p className="text-[11px] text-muted-stitch mt-3">Self-hosting behind your own proxy? Point <span className="font-mono-stitch">status.yourdomain.com</span> at this app and it serves <span className="font-mono-stitch">/status</span> directly.</p>
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
