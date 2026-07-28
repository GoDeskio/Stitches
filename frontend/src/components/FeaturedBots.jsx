import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, ArrowUpRight, TrendingUp } from "lucide-react";
import api from "@/lib/api";
import { Sparkline } from "@/components/Sparkline";

export default function FeaturedBots() {
  const [bots, setBots] = useState(null);
  const navigate = useNavigate();
  useEffect(() => { api.get("/bots/featured").then(({ data }) => setBots(data.bots)).catch(() => setBots([])); }, []);
  if (!bots || bots.length === 0) return null;
  return (
    <div className="neu-raised rounded-[1.75rem] p-7 animate-fade-up mt-6" data-testid="featured-bots-widget">
      <div className="flex items-center justify-between mb-5">
        <h2 className="font-head font-bold text-2xl flex items-center gap-2" style={{ color: "var(--text)" }}>
          <TrendingUp className="w-6 h-6 text-primary-stitch" /> Featured bots
        </h2>
        <button onClick={() => navigate("/bots")} className="text-sm text-primary-stitch font-semibold flex items-center gap-1" data-testid="featured-view-all">
          Browse directory <ArrowUpRight className="w-4 h-4" />
        </button>
      </div>
      <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {bots.map((b) => (
          <button key={b.bot_id} data-testid="featured-bot-card" onClick={() => navigate("/bots")}
            className="neu-pressed neu-hover rounded-2xl p-4 text-left flex items-start gap-3">
            <div className="neu-sm w-10 h-10 rounded-2xl flex items-center justify-center shrink-0"><Bot className="w-5 h-5 text-primary-stitch" /></div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold truncate flex items-center gap-2" style={{ color: "var(--text)" }}>
                {b.name}
                <span className="text-[10px] uppercase font-bold px-2 py-0.5 rounded-full text-primary-stitch shrink-0" style={{ background: "var(--neu-dark)" }}>{b.category}</span>
              </p>
              <p className="text-xs text-muted-stitch truncate">by {b.owner_name} · {b.recent} this week</p>
              <div className="mt-1.5"><Sparkline data={b.activity} w={110} h={22} /></div>
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
