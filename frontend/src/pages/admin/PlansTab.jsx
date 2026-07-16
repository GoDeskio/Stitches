import { useEffect, useState } from "react";
import { toast } from "sonner";
import api from "@/lib/api";
import { Loader } from "@/components/Stitch";
import { Tag, Plus, Pencil, Trash2, Star, ExternalLink } from "lucide-react";

const fmtMoney = (n) => "$" + (Number(n) || 0).toLocaleString(undefined, { maximumFractionDigits: 2 });
const intervalLabel = { month: "/mo", year: "/yr", once: " one-time" };

const EMPTY = { name: "", description: "", price: "", interval: "month", featuresText: "", highlighted: false, cta: "Get started", sort_order: 0, active: true };

export function PlansTab() {
  const [plans, setPlans] = useState(null);
  const [editing, setEditing] = useState(null); // plan object or {} for new

  const load = () => api.get("/admin/plans").then(({ data }) => setPlans(data.plans)).catch(() => setPlans([]));
  useEffect(() => { load(); }, []);

  const toggleActive = async (p) => {
    await api.put(`/admin/plans/${p.plan_id}`, { ...p, features: p.features, active: !p.active });
    load();
  };
  const del = async (p) => {
    if (!window.confirm(`Delete plan "${p.name}"?`)) return;
    await api.delete(`/admin/plans/${p.plan_id}`); toast.success("Plan deleted"); load();
  };

  if (!plans) return <Loader />;

  return (
    <div className="space-y-6" data-testid="plans-tab">
      <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up">
        <div className="flex items-center justify-between gap-3 flex-wrap mb-5">
          <div className="flex items-center gap-3">
            <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center"><Tag className="w-5 h-5 text-primary-stitch" /></div>
            <div>
              <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Pricing plans</h3>
              <p className="text-sm text-muted-stitch">Create and edit the plans shown on your public pricing page.</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <a href="/pricing" target="_blank" rel="noreferrer" data-testid="plans-view-page" className="neu-btn rounded-2xl px-4 py-2.5 text-sm font-semibold text-primary-stitch flex items-center gap-1.5"><ExternalLink className="w-4 h-4" /> View page</a>
            <button data-testid="plans-add-btn" onClick={() => setEditing({ ...EMPTY })} className="neu-primary rounded-2xl px-4 py-2.5 text-sm font-semibold flex items-center gap-1.5"><Plus className="w-4 h-4" /> Add plan</button>
          </div>
        </div>

        {plans.length === 0 ? (
          <p className="text-sm text-muted-stitch py-8 text-center">No plans yet. Add your first plan to build a pricing page.</p>
        ) : (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {plans.map((p) => (
              <div key={p.plan_id} data-testid="plan-card" className={`neu-pressed rounded-2xl p-5 ${p.active ? "" : "opacity-55"}`}>
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-head font-bold text-lg truncate flex items-center gap-1.5" style={{ color: "var(--text)" }}>
                      {p.name}{p.highlighted && <Star className="w-4 h-4 text-primary-stitch" fill="currentColor" />}
                    </p>
                    <p className="text-2xl font-head font-black mt-1" style={{ color: "var(--text)" }}>{fmtMoney(p.price)}<span className="text-sm font-normal text-muted-stitch">{intervalLabel[p.interval] || ""}</span></p>
                  </div>
                  <div className="flex gap-1 shrink-0">
                    <button data-testid="plan-edit-btn" onClick={() => setEditing({ ...p, featuresText: (p.features || []).join("\n") })} className="neu-btn rounded-xl px-2.5 py-2 text-primary-stitch"><Pencil className="w-4 h-4" /></button>
                    <button data-testid="plan-delete-btn" onClick={() => del(p)} className="neu-btn rounded-xl px-2.5 py-2 text-red-500"><Trash2 className="w-4 h-4" /></button>
                  </div>
                </div>
                {p.description && <p className="text-xs text-muted-stitch mt-2 line-clamp-2">{p.description}</p>}
                <ul className="mt-3 space-y-1">
                  {(p.features || []).slice(0, 4).map((f, i) => <li key={i} className="text-xs text-muted-stitch">• {f}</li>)}
                  {(p.features || []).length > 4 && <li className="text-xs text-muted-stitch">+ {p.features.length - 4} more</li>}
                </ul>
                <div className="flex items-center justify-between mt-4">
                  <span className="text-[11px] text-muted-stitch">Order: {p.sort_order}</span>
                  <button data-testid="plan-active-toggle" onClick={() => toggleActive(p)}
                    className={`w-12 h-7 rounded-full flex items-center px-1 transition-all ${p.active ? "justify-end" : "justify-start"}`}
                    style={{ background: p.active ? "var(--primary)" : "var(--neu-dark)" }}>
                    <span className="w-5 h-5 rounded-full bg-white shadow" />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {editing && <PlanEditor plan={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
}

function PlanEditor({ plan, onClose, onSaved }) {
  const [f, setF] = useState(plan);
  const [saving, setSaving] = useState(false);
  const set = (k, v) => setF((p) => ({ ...p, [k]: v }));
  const isNew = !plan.plan_id;

  const save = async () => {
    if (!f.name.trim()) { toast.error("Name is required"); return; }
    setSaving(true);
    const body = {
      name: f.name, description: f.description, price: parseFloat(f.price) || 0, interval: f.interval,
      features: (f.featuresText || "").split("\n").map((x) => x.trim()).filter(Boolean),
      highlighted: !!f.highlighted, cta: f.cta || "Get started",
      sort_order: parseInt(f.sort_order) || 0, active: f.active !== false,
    };
    try {
      if (isNew) await api.post("/admin/plans", body);
      else await api.put(`/admin/plans/${plan.plan_id}`, body);
      toast.success(isNew ? "Plan created" : "Plan saved");
      onSaved();
    } catch (e) { toast.error(e?.response?.data?.detail || "Failed"); } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50" onClick={onClose} data-testid="plan-editor-modal">
      <div className="neu-raised rounded-[1.75rem] p-6 max-w-lg w-full max-h-[88vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <h3 className="font-head font-bold text-xl mb-4" style={{ color: "var(--text)" }}>{isNew ? "Add plan" : "Edit plan"}</h3>
        <div className="space-y-3">
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs font-semibold text-muted-stitch">Name *</label>
              <input data-testid="plan-name" value={f.name} onChange={(e) => set("name", e.target.value)} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>
            <div className="w-28">
              <label className="text-xs font-semibold text-muted-stitch">Order</label>
              <input data-testid="plan-sort" type="number" value={f.sort_order} onChange={(e) => set("sort_order", e.target.value)} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-stitch">Description</label>
            <input data-testid="plan-desc" value={f.description} onChange={(e) => set("description", e.target.value)} placeholder="Short tagline" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs font-semibold text-muted-stitch">Price</label>
              <input data-testid="plan-price" type="number" step="0.01" min="0" value={f.price} onChange={(e) => set("price", e.target.value)} placeholder="0 = free" className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>
            <div className="flex-1">
              <label className="text-xs font-semibold text-muted-stitch">Billing</label>
              <select data-testid="plan-interval" value={f.interval} onChange={(e) => set("interval", e.target.value)} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1">
                <option value="month">per month</option>
                <option value="year">per year</option>
                <option value="once">one-time</option>
              </select>
            </div>
          </div>
          <div>
            <label className="text-xs font-semibold text-muted-stitch">Features (one per line)</label>
            <textarea data-testid="plan-features" value={f.featuresText} onChange={(e) => set("featuresText", e.target.value)} rows={5} placeholder={"Unlimited projects\nPriority support\nAdvanced analytics"} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1 resize-none" />
          </div>
          <div className="flex gap-3">
            <div className="flex-1">
              <label className="text-xs font-semibold text-muted-stitch">Button text</label>
              <input data-testid="plan-cta" value={f.cta} onChange={(e) => set("cta", e.target.value)} className="neu-input w-full rounded-2xl py-3 px-4 text-sm mt-1" />
            </div>
            <div className="flex items-center gap-4 pt-6">
              <label className="flex items-center gap-2 text-sm text-muted-stitch cursor-pointer">
                <input data-testid="plan-highlighted" type="checkbox" checked={!!f.highlighted} onChange={(e) => set("highlighted", e.target.checked)} /> Popular
              </label>
              <label className="flex items-center gap-2 text-sm text-muted-stitch cursor-pointer">
                <input data-testid="plan-active" type="checkbox" checked={f.active !== false} onChange={(e) => set("active", e.target.checked)} /> Active
              </label>
            </div>
          </div>
        </div>
        <div className="flex gap-3 mt-5">
          <button data-testid="plan-save-btn" onClick={save} disabled={saving} className="neu-primary rounded-2xl px-6 py-3 font-semibold flex-1">{saving ? "Saving…" : isNew ? "Create plan" : "Save changes"}</button>
          <button onClick={onClose} className="neu-btn rounded-2xl px-6 py-3 font-semibold">Cancel</button>
        </div>
      </div>
    </div>
  );
}
