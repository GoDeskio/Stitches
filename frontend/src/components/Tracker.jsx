import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import axios from "axios";
import { API } from "@/lib/api";

const PUBLIC_REF = new Set(["/", "/login", "/qr-login/claim"]);

async function maybeCaptureReference(path) {
  const key = "heat_ref_" + path;
  if (localStorage.getItem(key)) return;
  try {
    const { data } = await axios.get(`${API}/track/reference`, { params: { path } });
    if (!data.needed) { localStorage.setItem(key, "1"); return; }
  } catch (e) { return; }
  setTimeout(async () => {
    try {
      const html2canvas = (await import("html2canvas")).default;
      const shot = await html2canvas(document.body, { scale: 0.5, logging: false, useCORS: true, backgroundColor: "#1c1417", windowWidth: document.documentElement.scrollWidth });
      const w = 960, h = Math.round(w * (shot.height / shot.width));
      const out = document.createElement("canvas");
      out.width = w; out.height = h;
      out.getContext("2d").drawImage(shot, 0, 0, w, h);
      const img = out.toDataURL("image/jpeg", 0.5);
      if (img.length <= 1_600_000) {
        await axios.post(`${API}/track/reference`, { path, image: img });
        localStorage.setItem(key, "1");
      }
    } catch (e) { /* ignore */ }
  }, 2600);
}

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
    if (PUBLIC_REF.has(loc.pathname)) maybeCaptureReference(loc.pathname);
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
