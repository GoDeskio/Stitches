import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Loader } from "@/components/Stitch";
import { DownloadCloud, RefreshCw, GitBranch, Github, CheckCircle2, AlertTriangle, Server, ShieldCheck } from "lucide-react";

const short = (s) => (s || "").slice(0, 10);

export function UpdatesTab() {
  const [cfg, setCfg] = useState(null);
  const [f, setF] = useState({ repo_url: "", branch: "main", token: "", enabled: true, auto_apply: false });
  const [saving, setSaving] = useState(false);
  const [checking, setChecking] = useState(false);
  const [check, setCheck] = useState(null);
  const [job, setJob] = useState(null);
  const poll = useRef(null);

  const loadCfg = () => api.get("/admin/updates/config").then(({ data }) => {
    setCfg(data);
    setF({ repo_url: data.repo_url, branch: data.branch, token: "", enabled: data.enabled, auto_apply: data.auto_apply });
  });
  const loadStatus = () => api.get("/admin/updates/status").then(({ data }) => {
    setJob(data.job);
    if (data.job && data.job.status === "running" && !poll.current) startPoll();
    if (data.job && data.job.status !== "running") stopPoll();
  }).catch(() => {});

  useEffect(() => { loadCfg(); loadStatus(); return () => stopPoll(); }, []);

  const startPoll = () => { if (poll.current) return; poll.current = setInterval(loadStatus, 2500); };
  const stopPoll = () => { if (poll.current) { clearInterval(poll.current); poll.current = null; } };

  const save = async () => {
    setSaving(true);
    try {
      const body = { repo_url: f.repo_url, branch: f.branch, enabled: f.enabled, auto_apply: f.auto_apply };
      if (f.token) body.token = f.token;
      const { data } = await api.post("/admin/updates/config", body);
      setCfg(data); setF((p) => ({ ...p, token: "" }));
      toast.success("Update settings saved");
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed to save"); } finally { setSaving(false); }
  };

  const runCheck = async () => {
    setChecking(true);
    try {
      const { data } = await api.post("/admin/updates/check");
      setCheck(data); loadCfg();
      toast[data.update_available ? "info" : "success"](data.update_available ? "Update available!" : "You're up to date");
    } catch (e) { toast.error(e?.response?.data?.detail || "Check failed"); } finally { setChecking(false); }
  };

  const apply = async () => {
    if (!window.confirm("Apply the latest update now? This will pull the latest code, rebuild and restart the site.")) return;
    try {
      const { data } = await api.post("/admin/updates/apply");
      if (data.managed) { toast.info("Deploys are managed by the platform on this instance"); setJob({ status: "managed", logs: [data.message] }); return; }
      toast.success("Update started"); startPoll(); loadStatus();
    } catch (e) { toast.error(e?.response?.data?.detail || "Apply failed"); }
  };

  if (!cfg) return <Loader />;

  const avail = check ? check.update_available : cfg.update_available;

  return (
    <div className="space-y-6" data-testid="updates-tab">
      {/* Status card */}
      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        <div className="flex items-center gap-3 mb-5">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><DownloadCloud className="w-5 h-5 text-primary-stitch" /></div>
          <div>
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Software updates</h3>
            <p className="text-sm text-muted-stitch">Keep your site current with the latest code from GitHub.</p>
          </div>
        </div>

        <div className="grid sm:grid-cols-3 gap-4">
          <div className="neu-pressed rounded-2xl p-4">
            <p className="text-xs text-muted-stitch">Installed version</p>
            <p className="font-head font-bold text-lg" style={{ color: "var(--text)" }} data-testid="updates-version">v{cfg.version || "—"}</p>
            <p className="text-[11px] text-muted-stitch font-mono-stitch">{short(cfg.current_sha) || "no git"}</p>
          </div>
          <div className="neu-pressed rounded-2xl p-4">
            <p className="text-xs text-muted-stitch">Environment</p>
            <p className="font-head font-bold text-lg flex items-center gap-1.5" style={{ color: "var(--text)" }}>
              <Server className="w-4 h-4" />{cfg.self_hosted ? "Self-hosted" : "Managed"}
            </p>
            <p className="text-[11px] text-muted-stitch">{cfg.self_hosted ? "Auto-apply enabled" : "Deploys via platform"}</p>
          </div>
          <div className="neu-pressed rounded-2xl p-4">
            <p className="text-xs text-muted-stitch">Status</p>
            <p className={`font-head font-bold text-lg flex items-center gap-1.5 ${avail ? "text-primary-stitch" : ""}`} style={avail ? {} : { color: "var(--text)" }} data-testid="updates-status">
              {avail ? <><AlertTriangle className="w-4 h-4" /> Update available</> : <><CheckCircle2 className="w-4 h-4 text-green-500" /> Up to date</>}
            </p>
            {cfg.last_check && <p className="text-[11px] text-muted-stitch">Checked {new Date(cfg.last_check).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</p>}
          </div>
        </div>

        {(check?.latest || cfg.latest_sha) && (
          <div className="neu-pressed rounded-2xl p-4 mt-4">
            <p className="text-xs text-muted-stitch mb-1">Latest on GitHub</p>
            <p className="text-sm" style={{ color: "var(--text)" }}>{check?.latest?.message || cfg.latest_message}</p>
            <p className="text-[11px] text-muted-stitch font-mono-stitch mt-1">{short(check?.latest?.sha || cfg.latest_sha)} · {(check?.latest?.date || cfg.latest_date || "").slice(0, 10)}</p>
          </div>
        )}

        <div className="flex flex-wrap gap-3 mt-5">
          <button data-testid="updates-check-btn" onClick={runCheck} disabled={checking} className="neu-btn rounded-2xl px-5 py-3 font-semibold text-sm text-primary-stitch flex items-center gap-2 disabled:opacity-50">
            <RefreshCw className={`w-4 h-4 ${checking ? "animate-spin" : ""}`} /> {checking ? "Checking…" : "Check for updates"}
          </button>
          <button data-testid="updates-apply-btn" onClick={apply} disabled={job?.status === "running"} className="neu-primary rounded-2xl px-5 py-3 font-semibold text-sm flex items-center gap-2 disabled:opacity-50">
            <DownloadCloud className="w-4 h-4" /> {job?.status === "running" ? "Updating…" : "Apply update"}
          </button>
        </div>

        <div className="neu-pressed rounded-2xl p-4 mt-4 flex items-start gap-2.5" data-testid="updates-data-safety">
          <ShieldCheck className="w-4 h-4 text-green-500 mt-0.5 shrink-0" />
          <p className="text-xs text-muted-stitch">
            <span className="font-semibold" style={{ color: "var(--text)" }}>Your data is safe.</span> Updates replace application code only. All users, admin &amp; site data (MongoDB), uploaded files (object storage) and your <span className="font-mono-stitch">.env</span> config are preserved — and a backup is taken automatically before every update.
          </p>
        </div>

        {job && (job.logs?.length > 0) && (
          <div className="mt-4">
            <p className="text-xs font-semibold text-muted-stitch mb-1">Update log <span className="uppercase">· {job.status}</span></p>
            <pre data-testid="updates-log" className="neu-pressed rounded-2xl p-4 text-[11px] font-mono-stitch overflow-auto max-h-56" style={{ color: "var(--text)" }}>{(job.logs || []).join("\n")}</pre>
          </div>
        )}
      </div>

      {/* Repo config */}
      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        <h3 className="font-head font-bold text-xl mb-1" style={{ color: "var(--text)" }}>Update source</h3>
        <p className="text-sm text-muted-stitch mb-4">The GitHub repository this site updates from.</p>
        <div className="space-y-3">
          <div>
            <label className="text-xs font-semibold text-muted-stitch flex items-center gap-1.5"><Github className="w-3.5 h-3.5" /> Repository URL</label>
            <input data-testid="updates-repo" value={f.repo_url} onChange={(e) => setF((p) => ({ ...p, repo_url: e.target.value }))} placeholder="https://github.com/owner/repo.git" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 font-mono-stitch" />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs font-semibold text-muted-stitch flex items-center gap-1.5"><GitBranch className="w-3.5 h-3.5" /> Branch</label>
              <input data-testid="updates-branch" value={f.branch} onChange={(e) => setF((p) => ({ ...p, branch: e.target.value }))} placeholder="main" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 font-mono-stitch" />
            </div>
            <div className="flex-1">
              <label className="text-xs font-semibold text-muted-stitch">Access token {cfg.has_token && <span className="text-green-500">· set</span>}</label>
              <input data-testid="updates-token" type="password" value={f.token} onChange={(e) => setF((p) => ({ ...p, token: e.target.value }))} placeholder={cfg.has_token ? "•••• leave blank to keep" : "for private repos"} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>
          </div>
          <div className="flex flex-wrap gap-4 pt-1">
            <Toggle label="Enable update checks" testid="updates-enabled" on={f.enabled} onToggle={() => setF((p) => ({ ...p, enabled: !p.enabled }))} />
            <Toggle label="Auto-apply on new version (self-hosted only)" testid="updates-autoapply" on={f.auto_apply} onToggle={() => setF((p) => ({ ...p, auto_apply: !p.auto_apply }))} />
          </div>
          {f.auto_apply && !cfg.self_hosted && (
            <p className="text-xs text-amber-500 flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5" /> Auto-apply only runs on a self-hosted server (SELF_HOSTED=true). On this managed instance it just notifies you.</p>
          )}
          <button data-testid="updates-save-btn" onClick={save} disabled={saving} className="neu-primary rounded-2xl px-6 py-3 font-semibold text-sm mt-2">{saving ? "Saving…" : "Save settings"}</button>
        </div>
      </div>
    </div>
  );
}

function Toggle({ label, on, onToggle, testid }) {
  return (
    <button type="button" data-testid={testid} onClick={onToggle} className="flex items-center gap-2.5 text-sm text-muted-stitch">
      <span className={`w-11 h-6 rounded-full flex items-center px-1 transition-all ${on ? "justify-end" : "justify-start"}`} style={{ background: on ? "var(--primary)" : "var(--neu-dark)" }}>
        <span className="w-4 h-4 rounded-full bg-white shadow" />
      </span>
      {label}
    </button>
  );
}
