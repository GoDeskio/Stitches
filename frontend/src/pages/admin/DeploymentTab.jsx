import { useState, useEffect } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Rocket, Github, Copy, Check, Download, Server, ShieldCheck, Zap, AlertTriangle, X, Plus } from "lucide-react";

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
  const importPreset = async () => {
    const code = window.prompt("Paste a preset code to import:");
    if (!code || !code.trim()) return;
    try {
      const obj = JSON.parse(decodeURIComponent(escape(atob(code.trim()))));
      if (!obj.name || !Array.isArray(obj.ids)) throw new Error("bad");
      const ids = obj.ids.filter((i) => cat.catalog.some((c) => c.id === i));
      const adds = ids.filter((i) => !selected.includes(i));
      const removes = selected.filter((i) => !ids.includes(i));
      setImportPreview({ name: obj.name, ids, adds, removes });
    } catch (err) { toast.error("Invalid preset code"); }
  };
  const confirmImport = async () => {
    if (!importPreview) return;
    try {
      await api.post("/admin/deploy/presets", { name: importPreview.name, selected: importPreview.ids });
      setSelected(importPreview.ids);
      toast.success(`Imported "${importPreview.name}"`);
      setImportPreview(null);
      load();
    } catch (err) { toast.error(err?.response?.data?.detail || "Import failed"); }
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
            <h3 className="font-head font-bold text-xl mb-1" style={{ color: "var(--text)" }}>Import "{importPreview.name}"</h3>
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
              <button data-testid="import-confirm-btn" onClick={confirmImport} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex-1">Apply preset</button>
              <button data-testid="import-cancel-btn" onClick={() => setImportPreview(null)} className="neu-btn rounded-2xl px-5 py-3 font-semibold text-muted-stitch">Cancel</button>
            </div>
          </div>
        </div>
      )}
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
                <button key={p.id} data-testid={`deploy-preset-${p.id}`} onClick={() => setSelected(p.ids)}
                  className={`rounded-2xl px-4 py-2.5 text-sm font-semibold transition-all ${active ? "neu-primary" : "neu-pressed text-primary-stitch"}`}>
                  {p.label}
                </button>
              );
            })}
            {(cat.presets || []).map((p) => {
              const active = p.ids.length === selected.length && p.ids.every((i) => selected.includes(i));
              return (
                <span key={p.id} data-testid={`deploy-custom-preset-${p.id}`} onClick={() => setSelected(p.ids)}
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
