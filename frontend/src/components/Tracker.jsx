import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { API } from "@/lib/api";

function getVisitorId() {
  let v = localStorage.getItem("stitches_vid");
  if (!v) {
    v = "v_" + Math.random().toString(36).slice(2) + Date.now().toString(36);
    localStorage.setItem("stitches_vid", v);
  }
  return v;
}

function labelFor(el) {
  let node = el;
  for (let i = 0; i < 4 && node; i++) {
    if (node.getAttribute && node.getAttribute("data-testid")) return node.getAttribute("data-testid");
    node = node.parentElement;
  }
  const clickable = el.closest ? el.closest("button, a, [role=button]") : null;
  if (clickable) {
    const t = (clickable.getAttribute("data-testid") || clickable.getAttribute("aria-label") || clickable.innerText || "").trim();
    if (t) return t.slice(0, 60);
  }
  const txt = (el.innerText || "").trim();
  if (txt) return txt.slice(0, 60);
  return el.tagName ? el.tagName.toLowerCase() : "unknown";
}

// Site-wide, invisible activity collector. No visual output — the heatmap
// visualisation lives only in the Admin dashboard.
export default function Tracker() {
  const loc = useLocation();
  const queue = useRef([]);
  const vid = useRef(getVisitorId());

  useEffect(() => {
    queue.current.push({ type: "view", path: loc.pathname });
  }, [loc.pathname]);

  useEffect(() => {
    const flush = (beacon) => {
      if (!queue.current.length) return;
      const events = queue.current.splice(0, queue.current.length);
      const payload = JSON.stringify({ visitor_id: vid.current, events });
      const url = `${API}/track`;
      try {
        if (beacon && navigator.sendBeacon) {
          navigator.sendBeacon(url, new Blob([payload], { type: "application/json" }));
        } else {
          fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: payload, keepalive: true }).catch(() => {});
        }
      } catch (e) { /* ignore */ }
    };

    const onClick = (e) => {
      const sw = document.documentElement.scrollWidth || window.innerWidth;
      const sh = document.documentElement.scrollHeight || window.innerHeight;
      queue.current.push({
        type: "click",
        path: window.location.pathname,
        x: (e.pageX || 0) / (sw || 1),
        y: (e.pageY || 0) / (sh || 1),
        label: labelFor(e.target),
      });
      if (queue.current.length >= 20) flush(false);
    };

    document.addEventListener("click", onClick, true);
    const iv = setInterval(() => flush(false), 5000);
    const onHide = () => { if (document.visibilityState === "hidden") flush(true); };
    document.addEventListener("visibilitychange", onHide);
    window.addEventListener("pagehide", () => flush(true));

    return () => {
      document.removeEventListener("click", onClick, true);
      document.removeEventListener("visibilitychange", onHide);
      clearInterval(iv);
    };
  }, []);

  return null;
}
