import { useEffect, useState } from "react";
import { Download, X, Share } from "lucide-react";

const isIOS = () => /iphone|ipad|ipod/i.test(navigator.userAgent || "");
const isStandalone = () =>
  window.matchMedia?.("(display-mode: standalone)").matches || window.navigator.standalone === true;

export default function InstallPrompt() {
  const [deferred, setDeferred] = useState(null);
  const [ios, setIos] = useState(false);
  const [dismissed, setDismissed] = useState(() => localStorage.getItem("stitches_install_dismissed") === "1");

  useEffect(() => {
    const onPrompt = (e) => { e.preventDefault(); setDeferred(e); };
    window.addEventListener("beforeinstallprompt", onPrompt);
    if (isIOS() && !isStandalone()) setIos(true);
    return () => window.removeEventListener("beforeinstallprompt", onPrompt);
  }, []);

  const show = (deferred || ios) && !dismissed;
  if (!show) return null;

  const install = async () => {
    if (!deferred) return;
    deferred.prompt();
    try { await deferred.userChoice; } catch (e) {}
    setDeferred(null);
  };
  const close = () => { setDismissed(true); localStorage.setItem("stitches_install_dismissed", "1"); };

  return (
    <div data-testid="install-prompt" className="fixed bottom-4 left-4 z-40 neu-raised rounded-2xl p-4 flex items-center gap-4 max-w-sm animate-fade-up">
      <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center shrink-0">
        <img src="/icon-192.png" alt="" className="w-8 h-8 rounded-lg object-cover" />
      </div>
      <div className="flex-1 min-w-0">
        <p className="font-head font-bold text-sm" style={{ color: "var(--text)" }}>Install Stitches</p>
        {deferred ? (
          <p className="text-xs text-muted-stitch">Add it to your device for a faster, full-screen app.</p>
        ) : (
          <p className="text-xs text-muted-stitch flex items-center gap-1 flex-wrap" data-testid="install-ios-hint">
            Tap <Share className="w-3.5 h-3.5 inline text-primary-stitch" /> then <span className="font-semibold">Add to Home Screen</span>.
          </p>
        )}
      </div>
      {deferred && (
        <button data-testid="install-prompt-btn" onClick={install} className="neu-primary rounded-xl px-3 py-2 text-sm font-semibold flex items-center gap-1.5 shrink-0">
          <Download className="w-4 h-4" /> Install
        </button>
      )}
      <button data-testid="install-prompt-close" onClick={close} className="text-muted-stitch hover:text-primary-stitch shrink-0"><X className="w-4 h-4" /></button>
    </div>
  );
}
