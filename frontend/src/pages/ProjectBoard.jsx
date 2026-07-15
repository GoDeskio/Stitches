import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { ArrowLeft, Plus, Trash2, GripVertical } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageShell, Loader } from "@/components/Stitch";

const COLUMNS = [
  { key: "todo", label: "To Do" },
  { key: "doing", label: "In Progress" },
  { key: "done", label: "Done" },
];

export default function ProjectBoard() {
  const { projectId } = useParams();
  const navigate = useNavigate();
  const [project, setProject] = useState(null);
  const [tasks, setTasks] = useState(null);
  const [dragId, setDragId] = useState(null);
  const [adding, setAdding] = useState(null); // column key with open composer
  const [draft, setDraft] = useState("");

  const loadTasks = () => api.get(`/projects/${projectId}/tasks`).then(({ data }) => setTasks(data));
  useEffect(() => {
    api.get("/projects").then(({ data }) => setProject(data.find((p) => p.project_id === projectId) || { name: "Project" }));
    loadTasks();
  }, [projectId]); // eslint-disable-line

  const addTask = async (status) => {
    if (!draft.trim()) { setAdding(null); return; }
    const { data } = await api.post(`/projects/${projectId}/tasks`, { title: draft.trim(), status });
    setTasks((t) => [...t, data]);
    setDraft(""); setAdding(null);
  };

  const move = async (task, status) => {
    if (task.status === status) return;
    setTasks((t) => t.map((x) => x.task_id === task.task_id ? { ...x, status } : x));
    try { await api.put(`/tasks/${task.task_id}`, { status }); }
    catch (e) { toast.error("Could not move task"); loadTasks(); }
  };

  const remove = async (id) => {
    setTasks((t) => t.filter((x) => x.task_id !== id));
    await api.delete(`/tasks/${id}`);
  };

  if (tasks === null) return <PageShell><Loader /></PageShell>;

  return (
    <PageShell>
      <div className="flex items-center gap-4 mb-8 animate-fade-up">
        <button data-testid="board-back-btn" onClick={() => navigate("/projects")} className="neu-btn w-11 h-11 rounded-xl flex items-center justify-center text-primary-stitch"><ArrowLeft className="w-5 h-5" /></button>
        <div>
          <h1 className="font-head font-black text-4xl" style={{ color: "var(--text)" }}>{project?.name}</h1>
          <p className="text-muted-stitch text-sm">Task board — drag cards between columns to update status.</p>
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-6">
        {COLUMNS.map((col) => {
          const colTasks = tasks.filter((t) => t.status === col.key);
          return (
            <div key={col.key} data-testid={`board-column-${col.key}`}
              onDragOver={(e) => e.preventDefault()}
              onDrop={() => { if (dragId) { const t = tasks.find((x) => x.task_id === dragId); if (t) move(t, col.key); setDragId(null); } }}
              className="neu-pressed rounded-[1.5rem] p-4 flex flex-col min-h-[24rem]">
              <div className="flex items-center justify-between mb-4 px-1">
                <h3 className="font-head font-bold text-lg" style={{ color: "var(--text)" }}>{col.label}</h3>
                <span className="neu-sm text-xs px-2.5 py-1 rounded-full text-muted-stitch font-semibold">{colTasks.length}</span>
              </div>
              <div className="space-y-3 flex-1">
                {colTasks.map((t) => (
                  <div key={t.task_id} draggable data-testid="task-card"
                    onDragStart={() => setDragId(t.task_id)} onDragEnd={() => setDragId(null)}
                    className="neu-raised rounded-2xl p-4 group cursor-grab active:cursor-grabbing animate-fade-up">
                    <div className="flex items-start gap-2">
                      <GripVertical className="w-4 h-4 text-muted-stitch mt-0.5 shrink-0" />
                      <p className="text-sm flex-1 min-w-0" style={{ color: "var(--text)" }}>{t.title}</p>
                      <button data-testid="task-delete-btn" onClick={() => remove(t.task_id)} className="text-muted-stitch hover:text-primary-stitch opacity-0 group-hover:opacity-100 transition-opacity"><Trash2 className="w-3.5 h-3.5" /></button>
                    </div>
                    <div className="flex gap-1.5 mt-3">
                      {COLUMNS.filter((c) => c.key !== t.status).map((c) => (
                        <button key={c.key} data-testid="task-move-btn" onClick={() => move(t, c.key)}
                          className="neu-sm text-[10px] px-2 py-1 rounded-full text-muted-stitch hover:text-primary-stitch font-semibold">→ {c.label}</button>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              {adding === col.key ? (
                <div className="mt-3">
                  <textarea data-testid="task-input" autoFocus value={draft} onChange={(e) => setDraft(e.target.value)}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); addTask(col.key); } }}
                    placeholder="Task title…" rows={2} className="neu-input w-full rounded-2xl py-2.5 px-4 text-sm resize-none" />
                  <div className="flex gap-2 mt-2">
                    <button data-testid="task-add-submit" onClick={() => addTask(col.key)} className="neu-primary rounded-xl px-4 py-2 text-sm font-semibold flex-1">Add</button>
                    <button onClick={() => { setAdding(null); setDraft(""); }} className="neu-btn rounded-xl px-4 py-2 text-sm text-muted-stitch">Cancel</button>
                  </div>
                </div>
              ) : (
                <button data-testid={`add-task-${col.key}`} onClick={() => { setAdding(col.key); setDraft(""); }}
                  className="mt-3 neu-btn rounded-xl py-2.5 text-sm font-semibold text-muted-stitch hover:text-primary-stitch flex items-center justify-center gap-1.5">
                  <Plus className="w-4 h-4" /> Add task
                </button>
              )}
            </div>
          );
        })}
      </div>
    </PageShell>
  );
}
