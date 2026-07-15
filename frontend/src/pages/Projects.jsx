import { useEffect, useState } from "react";
import { Plus, FolderKanban, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageShell, PageHeader, Loader, EmptyState } from "@/components/Stitch";

const STATUSES = ["active", "planning", "on-hold", "completed"];

export default function Projects() {
  const [projects, setProjects] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState({ name: "", description: "", status: "active" });

  const load = () => api.get("/projects").then(({ data }) => setProjects(data));
  useEffect(() => { load(); }, []);

  const create = async (e) => {
    e.preventDefault();
    if (!form.name.trim()) return;
    await api.post("/projects", form);
    setShowModal(false); setForm({ name: "", description: "", status: "active" });
    toast.success("Project created"); load();
  };

  const cycleStatus = async (p) => {
    const next = STATUSES[(STATUSES.indexOf(p.status) + 1) % STATUSES.length];
    await api.put(`/projects/${p.project_id}`, { status: next });
    load();
  };

  const remove = async (id) => { await api.delete(`/projects/${id}`); toast.success("Project deleted"); load(); };

  if (projects === null) return <PageShell><Loader /></PageShell>;

  return (
    <PageShell>
      <PageHeader title="Projects" subtitle="Organise and track collaborative work across your teams."
        action={<button data-testid="new-project-btn" onClick={() => setShowModal(true)} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2"><Plus className="w-5 h-5" /> New Project</button>} />

      {projects.length === 0 ? (
        <EmptyState icon={FolderKanban} title="No projects yet" subtitle="Create your first project to start collaborating with your team."
          action={<button onClick={() => setShowModal(true)} className="neu-primary rounded-2xl px-6 py-3 font-semibold">Create Project</button>} />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {projects.map((p, i) => (
            <div key={p.project_id} className="neu-raised neu-hover rounded-[1.5rem] p-6 animate-fade-up flex flex-col" style={{ animationDelay: `${i * 50}ms` }} data-testid="project-card">
              <div className="flex items-start justify-between mb-4">
                <div className="neu-sm w-12 h-12 rounded-2xl flex items-center justify-center"><FolderKanban className="w-6 h-6 text-primary-stitch" /></div>
                <button onClick={() => remove(p.project_id)} className="text-muted-stitch hover:text-primary-stitch"><Trash2 className="w-4 h-4" /></button>
              </div>
              <h3 className="font-head font-bold text-xl mb-1" style={{ color: "var(--text)" }}>{p.name}</h3>
              <p className="text-sm text-muted-stitch flex-1 line-clamp-3">{p.description || "No description"}</p>
              <button onClick={() => cycleStatus(p)} className="neu-sm mt-4 self-start text-xs px-4 py-1.5 rounded-full capitalize text-primary-stitch font-semibold">{p.status}</button>
            </div>
          ))}
        </div>
      )}

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={() => setShowModal(false)}>
          <form onClick={(e) => e.stopPropagation()} onSubmit={create} className="neu-raised rounded-3xl p-8 w-full max-w-lg animate-fade-up">
            <div className="flex items-center justify-between mb-6">
              <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>New Project</h3>
              <button type="button" onClick={() => setShowModal(false)} className="text-muted-stitch"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-4">
              <input data-testid="project-name" autoFocus value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Project name" className="neu-input w-full rounded-2xl py-3.5 px-5" />
              <textarea data-testid="project-desc" value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description" rows={3} className="neu-input w-full rounded-2xl py-3.5 px-5 resize-none" />
              <div className="flex gap-2 flex-wrap">
                {STATUSES.map((s) => (
                  <button type="button" key={s} onClick={() => setForm({ ...form, status: s })}
                    className={`text-xs px-4 py-2 rounded-full capitalize font-semibold ${form.status === s ? "neu-primary" : "neu-sm text-muted-stitch"}`}>{s}</button>
                ))}
              </div>
            </div>
            <button data-testid="create-project-submit" type="submit" className="neu-primary w-full rounded-2xl py-3.5 font-semibold mt-6">Create Project</button>
          </form>
        </div>
      )}
    </PageShell>
  );
}
