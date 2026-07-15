import { useEffect, useState } from "react";
import {
  Plug, Cloud, Workflow, Sparkles, Server, X, Check, Trash2, ChevronRight, ArrowLeft,
  Play, HardDrive, Download, FolderOpen, Zap,
} from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageShell, PageHeader, Loader } from "@/components/Stitch";

const ICONS = { n8n: Workflow, aws_s3: HardDrive, dropbox: Cloud, google_drive: Cloud, llm: Sparkles, mcp: Server };

export default function Integrations() {
  const [catalog, setCatalog] = useState([]);
  const [connected, setConnected] = useState(null);
  const [wizard, setWizard] = useState(null);
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({});
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);
  const [runTarget, setRunTarget] = useState(null);
  const [filesTarget, setFilesTarget] = useState(null);

  const load = () => api.get("/integrations").then(({ data }) => setConnected(data));
  useEffect(() => {
    api.get("/integrations/catalog").then(({ data }) => setCatalog(data));
    load();
  }, []);

  const openWizard = (item) => { setWizard(item); setStep(0); setForm({}); setName(item.name); };
  const closeWizard = () => setWizard(null);

  const connect = async () => {
    setSaving(true);
    try {
      await api.post("/integrations", { type: wizard.type, name: name || wizard.name, config: form });
      toast.success(`${wizard.name} connected`);
      closeWizard(); load();
    } catch (e) { toast.error("Failed to connect"); } finally { setSaving(false); }
  };

  const remove = async (id) => { await api.delete(`/integrations/${id}`); toast.success("Disconnected"); load(); };

  const test = async (c) => {
    const tid = toast.loading("Testing connection…");
    try {
      const { data } = await api.post(`/integrations/${c.integration_id}/test`);
      toast[data.ok ? "success" : "error"](data.message || (data.ok ? "Connected" : "Failed"), { id: tid });
    } catch (e) { toast.error(e.response?.data?.detail || "Test failed", { id: tid }); }
  };

  if (connected === null) return <PageShell><Loader /></PageShell>;

  return (
    <PageShell>
      <PageHeader title="Integrations" subtitle="Connect N8N, cloud storage, AI LLMs and MCP servers with your own credentials. Trigger workflows and browse files right here." />

      {connected.length > 0 && (
        <div className="mb-10">
          <h2 className="font-head font-bold text-xl mb-4" style={{ color: "var(--text)" }}>Connected</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {connected.map((c) => {
              const Icon = ICONS[c.type] || Plug;
              const actions = c.actions || [];
              return (
                <div key={c.integration_id} className="neu-raised rounded-[1.5rem] p-6 flex flex-col gap-4 animate-fade-up" data-testid="connected-integration">
                  <div className="flex items-center gap-4">
                    <div className="neu-sm w-12 h-12 rounded-2xl flex items-center justify-center shrink-0"><Icon className="w-6 h-6 text-primary-stitch" /></div>
                    <div className="flex-1 min-w-0">
                      <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{c.name}</p>
                      <span className="text-xs text-green-500 flex items-center gap-1"><Check className="w-3 h-3" /> Connected</span>
                    </div>
                    <button data-testid="disconnect-integration" onClick={() => remove(c.integration_id)} className="text-muted-stitch hover:text-primary-stitch"><Trash2 className="w-4 h-4" /></button>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {actions.includes("run") && (
                      <button data-testid="integration-run-btn" onClick={() => setRunTarget(c)} className="neu-primary rounded-xl px-3 py-2 text-sm font-semibold flex items-center gap-1.5"><Play className="w-4 h-4" /> Run</button>
                    )}
                    {actions.includes("files") && (
                      <button data-testid="integration-files-btn" onClick={() => setFilesTarget(c)} className="neu-btn rounded-xl px-3 py-2 text-sm font-semibold text-primary-stitch flex items-center gap-1.5"><FolderOpen className="w-4 h-4" /> Browse files</button>
                    )}
                    {actions.includes("test") && (
                      <button data-testid="integration-test-btn" onClick={() => test(c)} className="neu-btn rounded-xl px-3 py-2 text-sm font-semibold text-muted-stitch flex items-center gap-1.5"><Zap className="w-4 h-4" /> Test</button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      <h2 className="font-head font-bold text-xl mb-4" style={{ color: "var(--text)" }}>Available</h2>
      <div className="grid sm:grid-cols-2 gap-6">
        {catalog.map((item, i) => {
          const Icon = ICONS[item.type] || Plug;
          return (
            <button key={item.type} onClick={() => openWizard(item)} data-testid={`integration-${item.type}`}
              className="neu-raised neu-hover rounded-[1.75rem] p-7 text-left flex items-center gap-5 animate-fade-up" style={{ animationDelay: `${i * 60}ms` }}>
              <div className="neu-sm w-16 h-16 rounded-3xl flex items-center justify-center shrink-0"><Icon className="w-8 h-8 text-primary-stitch" /></div>
              <div className="flex-1 min-w-0">
                <p className="text-xs uppercase tracking-widest text-muted-stitch mb-1">{item.category}</p>
                <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>{item.name}</h3>
                {item.description && <p className="text-sm text-muted-stitch mt-1 line-clamp-2">{item.description}</p>}
              </div>
              <ChevronRight className="w-6 h-6 text-muted-stitch shrink-0" />
            </button>
          );
        })}
      </div>

      {wizard && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={closeWizard}>
          <div onClick={(e) => e.stopPropagation()} className="neu-raised rounded-3xl p-8 w-full max-w-lg animate-fade-up">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-3">
                {step > 0 && <button onClick={() => setStep(step - 1)} className="text-muted-stitch"><ArrowLeft className="w-5 h-5" /></button>}
                <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>Connect {wizard.name}</h3>
              </div>
              <button onClick={closeWizard} className="text-muted-stitch"><X className="w-5 h-5" /></button>
            </div>
            <div className="flex gap-2 mb-6">
              {[0, 1].map((s) => <div key={s} className="h-1.5 flex-1 rounded-full" style={{ background: s <= step ? "var(--primary)" : "var(--border)" }} />)}
            </div>

            {step === 0 ? (
              <div className="animate-fade-up">
                <p className="text-muted-stitch mb-5">{wizard.description || "Give this connection a friendly name to identify it on your dashboard."}</p>
                <label className="text-sm font-semibold text-muted-stitch">Connection name</label>
                <input data-testid="wizard-name" value={name} onChange={(e) => setName(e.target.value)} className="neu-input w-full rounded-2xl py-3.5 px-5 mt-2 mb-6" />
                <button data-testid="wizard-next" onClick={() => setStep(1)} className="neu-primary w-full rounded-2xl py-3.5 font-semibold">Continue</button>
              </div>
            ) : (
              <div className="animate-fade-up space-y-4">
                <p className="text-muted-stitch">Enter your own credentials. They're stored securely and masked afterwards.</p>
                {wizard.fields.map((f) => (
                  <div key={f.key}>
                    <label className="text-sm font-semibold text-muted-stitch">{f.label}</label>
                    <input data-testid={`wizard-field-${f.key}`} type={f.type === "password" ? "password" : "text"}
                      value={form[f.key] || ""} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })}
                      className="neu-input w-full rounded-2xl py-3.5 px-5 mt-2" />
                  </div>
                ))}
                <button data-testid="wizard-connect" onClick={connect} disabled={saving} className="neu-primary w-full rounded-2xl py-3.5 font-semibold mt-2">
                  {saving ? "Connecting..." : "Connect"}
                </button>
              </div>
            )}
          </div>
        </div>
      )}

      {runTarget && <RunModal integration={runTarget} onClose={() => setRunTarget(null)} />}
      {filesTarget && <FilesModal integration={filesTarget} onClose={() => setFilesTarget(null)} />}
    </PageShell>
  );
}

function RunModal({ integration, onClose }) {
  const [payload, setPayload] = useState('{\n  "message": "Hello from Stitches"\n}');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState(null);

  const run = async () => {
    let body = {};
    try { body = payload.trim() ? JSON.parse(payload) : {}; }
    catch (e) { toast.error("Payload must be valid JSON"); return; }
    setRunning(true); setResult(null);
    try {
      const { data } = await api.post(`/integrations/${integration.integration_id}/run`, { payload: body });
      setResult(data);
      toast[data.ok ? "success" : "error"](data.ok ? "Workflow triggered" : `Failed (${data.status_code})`);
    } catch (e) { toast.error(e.response?.data?.detail || "Failed to trigger"); }
    finally { setRunning(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="neu-raised rounded-3xl p-8 w-full max-w-lg animate-fade-up" data-testid="run-modal">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>Run {integration.name}</h3>
          <button onClick={onClose} className="text-muted-stitch"><X className="w-5 h-5" /></button>
        </div>
        <p className="text-sm text-muted-stitch mb-3">Send a JSON payload to your N8N webhook to trigger the workflow.</p>
        <textarea data-testid="run-payload" value={payload} onChange={(e) => setPayload(e.target.value)} rows={6}
          className="neu-input w-full rounded-2xl py-3 px-5 mb-4 font-mono text-sm resize-none" />
        <button data-testid="run-trigger-btn" onClick={run} disabled={running} className="neu-primary w-full rounded-2xl py-3.5 font-semibold flex items-center justify-center gap-2">
          <Play className="w-5 h-5" /> {running ? "Triggering…" : "Trigger workflow"}
        </button>
        {result && (
          <div data-testid="run-result" className="neu-pressed rounded-2xl p-4 mt-4">
            <p className="text-xs uppercase tracking-widest text-muted-stitch mb-1">Response ({result.status_code})</p>
            <pre className="text-xs whitespace-pre-wrap break-words" style={{ color: "var(--text)" }}>{result.response || "(empty)"}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

function FilesModal({ integration, onClose }) {
  const [files, setFiles] = useState(null);
  const [error, setError] = useState(null);

  const load = () => {
    setFiles(null); setError(null);
    api.get(`/integrations/${integration.integration_id}/files`)
      .then(({ data }) => setFiles(data.files || []))
      .catch((e) => { setError(e.response?.data?.detail || "Could not list files"); setFiles([]); });
  };
  useEffect(load, []); // eslint-disable-line

  const download = async (key) => {
    const tid = toast.loading("Preparing download…");
    try {
      const { data } = await api.post(`/integrations/${integration.integration_id}/download`, { key });
      toast.dismiss(tid);
      window.open(data.url, "_blank");
    } catch (e) { toast.error(e.response?.data?.detail || "Download failed", { id: tid }); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="neu-raised rounded-3xl p-8 w-full max-w-lg animate-fade-up flex flex-col max-h-[85vh]" data-testid="files-modal">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>{integration.name} — Files</h3>
          <button onClick={onClose} className="text-muted-stitch"><X className="w-5 h-5" /></button>
        </div>
        {files === null ? <Loader /> : error ? (
          <div className="neu-pressed rounded-2xl p-5 text-sm text-red-400" data-testid="files-error">{error}</div>
        ) : files.length === 0 ? (
          <p className="text-sm text-muted-stitch">No files found.</p>
        ) : (
          <div className="space-y-2 overflow-y-auto">
            {files.map((f) => (
              <div key={f.key} className="neu-pressed rounded-2xl p-3 flex items-center gap-3" data-testid="file-row">
                <div className="neu-sm w-9 h-9 rounded-xl flex items-center justify-center shrink-0"><FolderOpen className="w-4 h-4 text-primary-stitch" /></div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{f.name}</p>
                  {f.size > 0 && <p className="text-xs text-muted-stitch">{(f.size / 1024).toFixed(1)} KB</p>}
                </div>
                <button data-testid="file-download-btn" onClick={() => download(f.key)} className="neu-btn w-9 h-9 rounded-xl flex items-center justify-center text-primary-stitch"><Download className="w-4 h-4" /></button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
