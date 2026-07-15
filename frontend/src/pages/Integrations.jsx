import { useEffect, useState } from "react";
import { Plug, Cloud, Workflow, Sparkles, Server, X, Check, Trash2, ChevronRight, ArrowLeft } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageShell, PageHeader, Loader } from "@/components/Stitch";

const ICONS = { n8n: Workflow, cloud_storage: Cloud, llm: Sparkles, mcp: Server };

export default function Integrations() {
  const [catalog, setCatalog] = useState([]);
  const [connected, setConnected] = useState(null);
  const [wizard, setWizard] = useState(null); // catalog item
  const [step, setStep] = useState(0);
  const [form, setForm] = useState({});
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

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

  if (connected === null) return <PageShell><Loader /></PageShell>;

  return (
    <PageShell>
      <PageHeader title="Integrations" subtitle="Connect N8N, cloud storage, AI LLMs and MCP servers. Wizards guide you through each connection." />

      {connected.length > 0 && (
        <div className="mb-10">
          <h2 className="font-head font-bold text-xl mb-4" style={{ color: "var(--text)" }}>Connected</h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            {connected.map((c) => {
              const Icon = ICONS[c.type] || Plug;
              return (
                <div key={c.integration_id} className="neu-raised rounded-[1.5rem] p-6 flex items-center gap-4 animate-fade-up" data-testid="connected-integration">
                  <div className="neu-sm w-12 h-12 rounded-2xl flex items-center justify-center shrink-0"><Icon className="w-6 h-6 text-primary-stitch" /></div>
                  <div className="flex-1 min-w-0">
                    <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{c.name}</p>
                    <span className="text-xs text-green-500 flex items-center gap-1"><Check className="w-3 h-3" /> Connected</span>
                  </div>
                  <button onClick={() => remove(c.integration_id)} className="text-muted-stitch hover:text-primary-stitch"><Trash2 className="w-4 h-4" /></button>
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
              <div className="flex-1">
                <p className="text-xs uppercase tracking-widest text-muted-stitch mb-1">{item.category}</p>
                <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>{item.name}</h3>
              </div>
              <ChevronRight className="w-6 h-6 text-muted-stitch" />
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
                <p className="text-muted-stitch mb-5">Give this connection a friendly name to identify it on your dashboard.</p>
                <label className="text-sm font-semibold text-muted-stitch">Connection name</label>
                <input data-testid="wizard-name" value={name} onChange={(e) => setName(e.target.value)} className="neu-input w-full rounded-2xl py-3.5 px-5 mt-2 mb-6" />
                <button data-testid="wizard-next" onClick={() => setStep(1)} className="neu-primary w-full rounded-2xl py-3.5 font-semibold">Continue</button>
              </div>
            ) : (
              <div className="animate-fade-up space-y-4">
                <p className="text-muted-stitch">Enter your credentials. They're stored securely and masked afterwards.</p>
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
    </PageShell>
  );
}
