import { useState, useRef, useEffect } from "react";
import { Sparkles, Send, User, Zap } from "lucide-react";
import api from "@/lib/api";
import { PageShell, PageHeader } from "@/components/Stitch";
import { useAuth } from "@/context/AuthContext";

const MODELS = [
  { label: "GPT-5.4", provider: "openai", model: "gpt-5.4" },
  { label: "Claude Sonnet 4.6", provider: "anthropic", model: "claude-sonnet-4-6" },
  { label: "Gemini 3.1 Pro", provider: "gemini", model: "gemini-3.1-pro-preview" },
];

const SUGGESTIONS = [
  "Create a project called Q3 Launch",
  "Create a workspace called Design Studio",
  "Show my dashboard stats",
];

export default function AiAssistant() {
  const { user } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [model, setModel] = useState(MODELS[0]);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, busy]);

  const send = async (text) => {
    const content = (text ?? input).trim();
    if (!content || busy) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content }]);
    setBusy(true);
    try {
      const { data } = await api.post("/ai/agent", { message: content, provider: model.provider, model: model.model });
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply || "Done.", result: data.result, action: data.action }]);
    } catch (e) {
      setMessages((prev) => [...prev, { role: "assistant", content: "Sorry, something went wrong reaching the AI." }]);
    } finally { setBusy(false); }
  };

  return (
    <PageShell>
      <PageHeader title="Stitch AI" subtitle="Your built-in AI assistant — ask anything, or tell it to create projects, workspaces, add connections and (as admin) manage the platform."
        action={
          <select data-testid="model-select" value={model.model} onChange={(e) => setModel(MODELS.find((m) => m.model === e.target.value))}
            className="neu-input rounded-2xl py-3 px-4 font-medium cursor-pointer" style={{ color: "var(--text)" }}>
            {MODELS.map((m) => <option key={m.model} value={m.model}>{m.label}</option>)}
          </select>
        } />

      <div className="neu-raised rounded-[1.75rem] flex flex-col" style={{ height: "calc(100vh - 260px)", minHeight: 420 }}>
        <div className="neu-pressed m-4 rounded-2xl flex-1 overflow-y-auto p-6 space-y-6">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center">
              <div className="neu-raised w-20 h-20 rounded-3xl flex items-center justify-center mb-6"><Sparkles className="w-9 h-9 text-primary-stitch" /></div>
              <h3 className="font-head font-bold text-2xl mb-2" style={{ color: "var(--text)" }}>How can I help you today?</h3>
              <p className="text-muted-stitch mb-6">Try one of these to get started</p>
              <div className="flex flex-col gap-3 w-full max-w-md">
                {SUGGESTIONS.map((s) => (
                  <button key={s} onClick={() => send(s)} className="neu-btn rounded-2xl py-3 px-5 text-sm text-left" style={{ color: "var(--text)" }}>{s}</button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((m, i) => (
              <div key={i} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                <div className="neu-sm w-9 h-9 rounded-full flex items-center justify-center shrink-0">
                  {m.role === "user" ? <User className="w-4 h-4 text-muted-stitch" /> : <Sparkles className="w-4 h-4 text-primary-stitch" />}
                </div>
                <div className={`max-w-[75%] rounded-2xl px-4 py-3 whitespace-pre-wrap text-[0.95rem] leading-relaxed`}
                  style={{ background: m.role === "user" ? "var(--primary)" : "var(--neu-light)", color: m.role === "user" ? "#fff" : "var(--text)" }}>
                  {m.content}
                  {m.action && m.result?.ok && (
                    <span data-testid="ai-action-chip" className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-full" style={{ background: "var(--surface)", color: "var(--primary)" }}>
                      <Zap className="w-3 h-3" /> {m.action.replace(/_/g, " ")}
                    </span>
                  )}
                  {m.result?.items?.length > 0 && (
                    <ul className="mt-2 space-y-1">
                      {m.result.items.map((it, k) => <li key={k} className="text-sm opacity-90">• {it}</li>)}
                    </ul>
                  )}
                </div>
              </div>
            ))
          )}
          {busy && (
            <div className="flex gap-3">
              <div className="neu-sm w-9 h-9 rounded-full flex items-center justify-center shrink-0"><Sparkles className="w-4 h-4 text-primary-stitch" /></div>
              <div className="rounded-2xl px-4 py-3" style={{ background: "var(--neu-light)" }}>
                <span className="flex gap-1">
                  <span className="w-2 h-2 rounded-full bg-current animate-bounce text-primary-stitch" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 rounded-full bg-current animate-bounce text-primary-stitch" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 rounded-full bg-current animate-bounce text-primary-stitch" style={{ animationDelay: "300ms" }} />
                </span>
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={(e) => { e.preventDefault(); send(); }} className="p-4 pt-0 flex gap-3">
          <input data-testid="ai-input" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Message Stitch AI..."
            className="neu-input flex-1 rounded-2xl py-3.5 px-5" />
          <button data-testid="ai-send-btn" type="submit" disabled={busy} className="neu-primary rounded-2xl px-6 flex items-center justify-center disabled:opacity-70">
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </PageShell>
  );
}
