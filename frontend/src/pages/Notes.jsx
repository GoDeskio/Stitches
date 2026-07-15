import { useEffect, useState } from "react";
import { Plus, StickyNote, Trash2, X, Pencil } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageShell, PageHeader, Loader, EmptyState } from "@/components/Stitch";

const COLORS = {
  default: "var(--neu-light)",
  amber: "#E0B44A",
  red: "#DC2626",
  green: "#3FB27F",
  blue: "#3B82F6",
  purple: "#8B5CF6",
};

export default function Notes() {
  const [notes, setNotes] = useState(null);
  const [editing, setEditing] = useState(null); // note object or {} for new

  const load = () => api.get("/notes").then(({ data }) => setNotes(data));
  useEffect(() => { load(); }, []);

  const remove = async (id) => { await api.delete(`/notes/${id}`); toast.success("Note deleted"); load(); };

  if (notes === null) return <PageShell><Loader /></PageShell>;

  return (
    <PageShell>
      <PageHeader title="Notes" subtitle="Jot down ideas, meeting notes and reminders. Your private notes, saved to your dashboard."
        action={<button data-testid="new-note-btn" onClick={() => setEditing({ title: "", content: "", color: "default" })} className="neu-primary rounded-2xl px-5 py-3 font-semibold flex items-center gap-2"><Plus className="w-5 h-5" /> New Note</button>} />

      {notes.length === 0 ? (
        <EmptyState icon={StickyNote} title="No notes yet" subtitle="Create your first note to keep track of ideas and information."
          action={<button onClick={() => setEditing({ title: "", content: "", color: "default" })} className="neu-primary rounded-2xl px-6 py-3 font-semibold">Create Note</button>} />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {notes.map((n, i) => (
            <div key={n.note_id} className="neu-raised neu-hover rounded-[1.5rem] p-6 animate-fade-up flex flex-col" style={{ animationDelay: `${i * 40}ms` }} data-testid="note-card">
              <div className="flex items-start justify-between mb-3 gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="w-3 h-3 rounded-full shrink-0" style={{ background: COLORS[n.color] || COLORS.default }} />
                  <h3 className="font-head font-bold text-lg truncate" style={{ color: "var(--text)" }}>{n.title || "Untitled"}</h3>
                </div>
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => setEditing(n)} className="text-muted-stitch hover:text-primary-stitch"><Pencil className="w-4 h-4" /></button>
                  <button onClick={() => remove(n.note_id)} className="text-muted-stitch hover:text-primary-stitch"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
              <p className="text-sm text-muted-stitch whitespace-pre-wrap line-clamp-6 flex-1">{n.content || "—"}</p>
              <p className="text-xs text-muted-stitch mt-4">{new Date(n.updated_at).toLocaleDateString()}</p>
            </div>
          ))}
        </div>
      )}

      {editing && <NoteEditor note={editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </PageShell>
  );
}

function NoteEditor({ note, onClose, onSaved }) {
  const [title, setTitle] = useState(note.title || "");
  const [content, setContent] = useState(note.content || "");
  const [color, setColor] = useState(note.color || "default");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      if (note.note_id) await api.put(`/notes/${note.note_id}`, { title, content, color });
      else await api.post("/notes", { title, content, color });
      toast.success("Note saved");
      onSaved();
    } catch (e) { toast.error("Failed to save"); } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-6" style={{ background: "rgba(0,0,0,0.5)" }} onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="neu-raised rounded-3xl p-8 w-full max-w-lg animate-fade-up">
        <div className="flex items-center justify-between mb-6">
          <h3 className="font-head font-bold text-2xl" style={{ color: "var(--text)" }}>{note.note_id ? "Edit Note" : "New Note"}</h3>
          <button onClick={onClose} className="text-muted-stitch"><X className="w-5 h-5" /></button>
        </div>
        <input data-testid="note-title-input" autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" className="neu-input w-full rounded-2xl py-3 px-5 mb-4" />
        <textarea data-testid="note-content-input" value={content} onChange={(e) => setContent(e.target.value)} placeholder="Write your note..." rows={6} className="neu-input w-full rounded-2xl py-3 px-5 mb-4 resize-none" />
        <div className="flex items-center gap-2 mb-6">
          {Object.entries(COLORS).map(([name, c]) => (
            <button key={name} onClick={() => setColor(name)}
              className={`w-8 h-8 rounded-full transition-transform ${color === name ? "scale-110 ring-2 ring-offset-2" : ""}`}
              style={{ background: c, ringColor: "var(--primary)", boxShadow: color === name ? "0 0 0 2px var(--primary)" : "none" }} />
          ))}
        </div>
        <button data-testid="save-note-btn" onClick={save} disabled={saving} className="neu-primary w-full rounded-2xl py-3.5 font-semibold">{saving ? "Saving..." : "Save Note"}</button>
      </div>
    </div>
  );
}
