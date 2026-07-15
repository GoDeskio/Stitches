import { useEffect, useState } from "react";
import { Plus, FolderKanban, Trash2, X, Users, UserMinus, UserPlus, Mail } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageShell, PageHeader, Loader, EmptyState } from "@/components/Stitch";

const STATUSES = ["active", "planning", "on-hold", "completed"];

export default function Projects() {
  const [projects, setProjects] = useState(null);
  const [showModal, setShowModal] = useState(false);
  const [memberProject, setMemberProject] = useState(null);
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
              <div className="flex items-center gap-2 mt-4">
                <button onClick={() => cycleStatus(p)} className="neu-sm text-xs px-4 py-1.5 rounded-full capitalize text-primary-stitch font-semibold">{p.status}</button>
                <button data-testid="project-members-btn" onClick={() => setMemberProject(p)} className="neu-btn text-xs px-4 py-1.5 rounded-full text-muted-stitch font-semibold flex items-center gap-1 ml-auto">
                  <Users className="w-3.5 h-3.5" /> Members
                </button>
              </div>
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
      {memberProject && <ProjectMembersModal project={memberProject} onClose={() => setMemberProject(null)} />}
    </PageShell>
  );
}

function ProjectMembersModal({ project, onClose }) {
  const [members, setMembers] = useState([]);
  const [friends, setFriends] = useState([]);
  const [email, setEmail] = useState("");
  const [inviting, setInviting] = useState(false);

  const load = () => api.get(`/projects/${project.project_id}/members`).then(({ data }) => setMembers(data));
  useEffect(() => { load(); api.get("/friends").then(({ data }) => setFriends(data)); }, []); // eslint-disable-line

  const inviteEmail = async (target) => { await api.post(`/projects/${project.project_id}/invite`, { email: target }); load(); };
  const invite = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setInviting(true);
    try { await inviteEmail(email.trim()); toast.success(`Added ${email.trim()}`); setEmail(""); }
    catch (err) { toast.error(err.response?.data?.detail || "Could not add"); } finally { setInviting(false); }
  };
  const quickAdd = async (f) => {
    try { await inviteEmail(f.email); toast.success(`Added ${f.name}`); }
    catch (err) { toast.error(err.response?.data?.detail || "Could not add"); }
  };
  const remove = async (uid) => {
    try { await api.post(`/projects/${project.project_id}/remove`, { user_id: uid }); toast.success("Removed"); load(); }
    catch (err) { toast.error(err.response?.data?.detail || "Could not remove"); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="neu-raised rounded-3xl p-8 w-full max-w-md animate-fade-up">
        <div className="flex items-center justify-between mb-6">
          <div>
            <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>Project Members</h3>
            <p className="text-sm text-muted-stitch">{project.name}</p>
          </div>
          <button onClick={onClose} className="text-muted-stitch"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={invite} className="flex gap-2 mb-6">
          <div className="relative flex-1">
            <Mail className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-muted-stitch" />
            <input data-testid="project-invite-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
              placeholder="Add member by email" className="neu-input w-full rounded-2xl py-3 pl-12 pr-4" />
          </div>
          <button data-testid="project-invite-btn" type="submit" disabled={inviting} className="neu-primary rounded-2xl px-5 font-semibold"><UserPlus className="w-5 h-5" /></button>
        </form>
        {friends.filter((f) => !members.some((m) => m.user_id === f.user_id)).length > 0 && (
          <div className="mb-5">
            <p className="text-xs uppercase tracking-widest text-muted-stitch mb-2">Add from your connections</p>
            <div className="flex flex-wrap gap-2">
              {friends.filter((f) => !members.some((m) => m.user_id === f.user_id)).map((f) => (
                <button key={f.user_id} data-testid="project-quick-add-friend" onClick={() => quickAdd(f)}
                  className="neu-btn rounded-full pl-2 pr-3 py-1.5 flex items-center gap-2 text-sm">
                  <span className="neu-sm w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold text-primary-stitch">{(f.name || "U")[0].toUpperCase()}</span>
                  <span style={{ color: "var(--text)" }}>{f.name}</span>
                  <UserPlus className="w-3.5 h-3.5 text-primary-stitch" />
                </button>
              ))}
            </div>
          </div>
        )}
        <div className="space-y-2 max-h-72 overflow-y-auto">
          {members.map((m) => (
            <div key={m.user_id} className="neu-pressed rounded-2xl p-3 flex items-center gap-3">
              <div className="neu-sm w-9 h-9 rounded-full flex items-center justify-center overflow-hidden shrink-0">
                {m.avatar ? <img src={m.avatar} alt="" className="w-full h-full object-cover" /> :
                  <span className="font-head font-bold text-sm text-primary-stitch">{(m.name || "U")[0].toUpperCase()}</span>}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold truncate" style={{ color: "var(--text)" }}>{m.name} {m.is_owner && <span className="text-xs text-muted-stitch">(owner)</span>}</p>
                <p className="text-xs text-muted-stitch truncate">{m.email}</p>
              </div>
              {!m.is_owner && (
                <button onClick={() => remove(m.user_id)} className="neu-btn w-8 h-8 rounded-lg flex items-center justify-center text-muted-stitch"><UserMinus className="w-4 h-4" /></button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
