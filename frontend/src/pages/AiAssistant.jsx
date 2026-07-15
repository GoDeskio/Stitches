import { useState, useRef, useEffect } from "react";
import { Sparkles, Send, User } from "lucide-react";
import { API } from "@/lib/api";
import { PageShell, PageHeader } from "@/components/Stitch";

const MODELS = [
  { label: "GPT-5.4", provider: "openai", model: "gpt-5.4" },
  { label: "Claude Sonnet 4.6", provider: "anthropic", model: "claude-sonnet-4-6" },
  { label: "Gemini 3.1 Pro", provider: "gemini", model: "gemini-3.1-pro-preview" },
];

const SUGGESTIONS = [
  "Draft a project kickoff message for my team",
  "Summarise best practices for creative collaboration",
  "Suggest a weekly workflow for a design studio",
];

export default function AiAssistant() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [model, setModel] = useState(MODELS[0]);
  const convId = useRef(null);
  const bottomRef = useRef(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  const send = async (text) => {
    const content = (text ?? input).trim();
    if (!content || streaming) return;
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content }, { role: "assistant", content: "" }]);
    setStreaming(true);

    try {
      const token = localStorage.getItem("stitches_token");
      const res = await fetch(`${API}/ai/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        credentials: "include",
        body: JSON.stringify({ message: content, provider: model.provider, model: model.model, conversation_id: convId.current }),
      });
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop();
        for (const line of lines) {
          if (!line.startsWith("data: ")) continue;
          const data = JSON.parse(line.slice(6));
          if (data.conversation_id) convId.current = data.conversation_id;
          if (data.delta) {
            setMessages((prev) => {
              const copy = [...prev];
              copy[copy.length - 1] = { role: "assistant", content: copy[copy.length - 1].content + data.delta };
              return copy;
            });
          }
        }
      }
    } catch (e) {
      setMessages((prev) => {
        const copy = [...prev];
        copy[copy.length - 1] = { role: "assistant", content: "Sorry, something went wrong reaching the AI." };
        return copy;
      });
    } finally { setStreaming(false); }
  };

  return (
    <PageShell>
      <PageHeader title="Stitch AI" subtitle="Your built-in AI assistant. Ask anything, brainstorm, or draft content for your team."
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
                  {m.content || (streaming && i === messages.length - 1 ? "…" : "")}
                </div>
              </div>
            ))
          )}
          <div ref={bottomRef} />
        </div>

        <form onSubmit={(e) => { e.preventDefault(); send(); }} className="p-4 pt-0 flex gap-3">
          <input data-testid="ai-input" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Message Stitch AI..."
            className="neu-input flex-1 rounded-2xl py-3.5 px-5" />
          <button data-testid="ai-send-btn" type="submit" disabled={streaming} className="neu-primary rounded-2xl px-6 flex items-center justify-center disabled:opacity-70">
            <Send className="w-5 h-5" />
          </button>
        </form>
      </div>
    </PageShell>
  );
}
