import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Users, UserPlus, UserMinus, Mail, MessageSquare } from "lucide-react";
import { toast } from "sonner";
import api from "@/lib/api";
import { PageShell, PageHeader, Loader, EmptyState } from "@/components/Stitch";

export default function People() {
  const navigate = useNavigate();
  const [friends, setFriends] = useState(null);
  const [email, setEmail] = useState("");
  const [adding, setAdding] = useState(false);

  const load = () => api.get("/friends").then(({ data }) => setFriends(data));
  useEffect(() => { load(); }, []);

  const add = async (e) => {
    e.preventDefault();
    if (!email.trim()) return;
    setAdding(true);
    try {
      await api.post("/friends", { email: email.trim() });
      toast.success("Connection added");
      setEmail(""); load();
    } catch (err) { toast.error(err.response?.data?.detail || "Could not add"); } finally { setAdding(false); }
  };

  const remove = async (id) => { await api.delete(`/friends/${id}`); toast.success("Connection removed"); load(); };
  const message = (id) => { localStorage.setItem("stitches_open_dm", id); navigate("/messages"); };

  if (friends === null) return <PageShell><Loader /></PageShell>;

  return (
    <PageShell>
      <PageHeader title="People" subtitle="Manage your connections. Add teammates so you can quickly invite them to workspaces and projects." />

      <form onSubmit={add} className="neu-raised rounded-[1.5rem] p-5 flex gap-3 mb-8 animate-fade-up">
        <div className="relative flex-1">
          <Mail className="w-5 h-5 absolute left-4 top-1/2 -translate-y-1/2 text-muted-stitch" />
          <input data-testid="add-friend-input" type="email" value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder="Add a connection by email" className="neu-input w-full rounded-2xl py-3.5 pl-12 pr-4" />
        </div>
        <button data-testid="add-friend-btn" type="submit" disabled={adding} className="neu-primary rounded-2xl px-6 font-semibold flex items-center gap-2">
          <UserPlus className="w-5 h-5" /> {adding ? "Adding..." : "Add"}
        </button>
      </form>

      {friends.length === 0 ? (
        <EmptyState icon={Users} title="No connections yet" subtitle="Add teammates by their email to build your network on Stitches." />
      ) : (
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
          {friends.map((f, i) => (
            <div key={f.user_id} className="neu-raised rounded-[1.5rem] p-6 flex items-center gap-4 animate-fade-up" style={{ animationDelay: `${i * 40}ms` }} data-testid="friend-card">
              <div className="relative neu-sm w-14 h-14 rounded-full flex items-center justify-center overflow-hidden shrink-0">
                {f.avatar ? <img src={f.avatar} alt="" className="w-full h-full object-cover" /> :
                  <span className="font-head font-bold text-xl text-primary-stitch">{(f.name || "U")[0].toUpperCase()}</span>}
                {f.online && <span className="absolute bottom-0 right-0 w-3.5 h-3.5 rounded-full bg-green-500 border-2" style={{ borderColor: "var(--surface)" }} />}
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold truncate" style={{ color: "var(--text)" }}>{f.name}</p>
                <p className="text-sm text-muted-stitch truncate">{f.online ? "● Online" : f.email}</p>
              </div>
              <button data-testid="message-friend-btn" onClick={() => message(f.user_id)} className="neu-btn w-10 h-10 rounded-xl flex items-center justify-center text-primary-stitch" title="Message">
                <MessageSquare className="w-4 h-4" />
              </button>
              <button onClick={() => remove(f.user_id)} className="neu-btn w-10 h-10 rounded-xl flex items-center justify-center text-muted-stitch" title="Remove">
                <UserMinus className="w-4 h-4" />
              </button>
            </div>
          ))}
        </div>
      )}
    </PageShell>
  );
}
