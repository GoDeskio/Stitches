import { useState } from "react";
import { Copy, Check, Terminal, Server, ChevronDown, ShieldCheck, Container, Package } from "lucide-react";

function CopyBlock({ label, code }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch (e) { /* clipboard unavailable */ }
  };
  return (
    <div className="mb-4" data-testid={`coturn-block-${label}`}>
      {label && <p className="text-xs font-semibold text-muted-stitch mb-1.5 uppercase tracking-wide">{label}</p>}
      <div className="neu-pressed rounded-2xl p-4 relative group">
        <button
          data-testid={`coturn-copy-${label}`}
          onClick={copy}
          className="neu-btn absolute top-3 right-3 rounded-xl px-2.5 py-1.5 text-xs font-semibold flex items-center gap-1.5 text-primary-stitch"
        >
          {copied ? <><Check className="w-3.5 h-3.5" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
        </button>
        <pre className="font-mono-stitch text-[12.5px] leading-relaxed whitespace-pre-wrap break-words pr-16" style={{ color: "var(--text)" }}>{code}</pre>
      </div>
    </div>
  );
}

const DOCKER_RUN = `# 1. Pick a strong shared secret + your server's PUBLIC IP
export TURN_SECRET="$(openssl rand -hex 32)"
export PUBLIC_IP="YOUR.SERVER.PUBLIC.IP"

# 2. Run coturn (official image) with the required UDP/TCP ports
docker run -d --name coturn --restart unless-stopped \\
  --network host \\
  coturn/coturn \\
  -n --log-file=stdout \\
  --min-port=49160 --max-port=49200 \\
  --lt-cred-mech --fingerprint \\
  --realm=stitches \\
  --user=stitches:$TURN_SECRET \\
  --external-ip=$PUBLIC_IP \\
  --listening-port=3478 --tls-listening-port=5349`;

const DOCKER_COMPOSE = `services:
  coturn:
    image: coturn/coturn
    network_mode: host
    restart: unless-stopped
    command: >
      -n --log-file=stdout
      --min-port=49160 --max-port=49200
      --lt-cred-mech --fingerprint
      --realm=stitches
      --user=stitches:REPLACE_WITH_SECRET
      --external-ip=YOUR.SERVER.PUBLIC.IP
      --listening-port=3478 --tls-listening-port=5349`;

const FIREWALL = `# Open the ports coturn needs on your firewall / cloud security group
sudo ufw allow 3478/tcp
sudo ufw allow 3478/udp
sudo ufw allow 5349/tcp
sudo ufw allow 5349/udp
sudo ufw allow 49160:49200/udp`;

const SRC_DEPS = `# Ubuntu / Debian — install coturn + its dependencies
sudo apt-get update
sudo apt-get install -y coturn \\
  libevent-2.1-7 libevent-core-2.1-7 \\
  libssl3 openssl \\
  libmicrohttpd12 sqlite3

# Dependencies explained:
#   libevent2      -> async network event loop (required)
#   openssl/libssl -> TLS for turns:/ secure relay
#   libmicrohttpd  -> optional admin web UI
#   sqlite3        -> lightweight user/credential store`;

const SRC_ENABLE = `# Enable the service so it starts on boot
sudo sed -i 's/#TURNSERVER_ENABLED=1/TURNSERVER_ENABLED=1/' /etc/default/coturn
echo "TURNSERVER_ENABLED=1" | sudo tee -a /etc/default/coturn`;

const SRC_CONF = `# /etc/turnserver.conf
listening-port=3478
tls-listening-port=5349
min-port=49160
max-port=49200

# Auth (long-term credentials)
lt-cred-mech
realm=stitches
user=stitches:REPLACE_WITH_STRONG_SECRET

# Your server's public IP (behind NAT / cloud)
external-ip=YOUR.SERVER.PUBLIC.IP

fingerprint
no-multicast-peers
# TLS certs (recommended for turns:)
# cert=/etc/ssl/certs/turn.crt
# pkey=/etc/ssl/private/turn.key`;

const SRC_START = `# Start & verify
sudo systemctl enable coturn
sudo systemctl restart coturn
sudo systemctl status coturn --no-pager`;

export function TurnSetupGuide() {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState("docker");

  return (
    <div className="neu-raised rounded-[1.75rem] p-6 animate-fade-up" data-testid="coturn-setup-guide">
      <button
        data-testid="coturn-guide-toggle"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between gap-3 text-left"
      >
        <div className="flex items-center gap-3 min-w-0">
          <div className="neu-sm w-11 h-11 rounded-2xl flex items-center justify-center shrink-0">
            <Terminal className="w-5 h-5 text-primary-stitch" />
          </div>
          <div className="min-w-0">
            <h3 className="font-head font-bold text-xl" style={{ color: "var(--text)" }}>Deploy your own Coturn server</h3>
            <p className="text-sm text-muted-stitch">Step-by-step guide to run a free, self-hosted TURN server — no third party needed.</p>
          </div>
        </div>
        <ChevronDown className={`w-5 h-5 shrink-0 text-muted-stitch transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="mt-6" data-testid="coturn-guide-body">
          <div className="neu-pressed rounded-2xl p-1.5 inline-flex gap-1.5 mb-6">
            <button
              data-testid="coturn-tab-docker"
              onClick={() => setMode("docker")}
              className={`rounded-xl px-4 py-2 text-sm font-semibold flex items-center gap-2 transition-all ${mode === "docker" ? "neu-primary" : "text-muted-stitch"}`}
            >
              <Container className="w-4 h-4" /> Docker (quickest)
            </button>
            <button
              data-testid="coturn-tab-source"
              onClick={() => setMode("source")}
              className={`rounded-xl px-4 py-2 text-sm font-semibold flex items-center gap-2 transition-all ${mode === "source" ? "neu-primary" : "text-muted-stitch"}`}
            >
              <Package className="w-4 h-4" /> From source (Ubuntu/Debian)
            </button>
          </div>

          {mode === "docker" && (
            <div data-testid="coturn-docker-panel">
              <p className="text-sm text-muted-stitch mb-4 flex items-start gap-2">
                <Container className="w-4 h-4 mt-0.5 shrink-0 text-primary-stitch" />
                Fastest path. Requires Docker on a machine with a <strong>public IP</strong> and open UDP ports. <code className="font-mono-stitch">--network host</code> is important so the relay ports are reachable.
              </p>
              <CopyBlock label="Run with Docker" code={DOCKER_RUN} />
              <CopyBlock label="Or use docker-compose.yml" code={DOCKER_COMPOSE} />
              <CopyBlock label="Open firewall ports" code={FIREWALL} />
            </div>
          )}

          {mode === "source" && (
            <div data-testid="coturn-source-panel">
              <p className="text-sm text-muted-stitch mb-4 flex items-start gap-2">
                <Server className="w-4 h-4 mt-0.5 shrink-0 text-primary-stitch" />
                Install coturn directly on a Linux VM. Best for a permanent, always-on server.
              </p>
              <CopyBlock label="1 · Install dependencies" code={SRC_DEPS} />
              <CopyBlock label="2 · Enable the service" code={SRC_ENABLE} />
              <CopyBlock label="3 · Configure /etc/turnserver.conf" code={SRC_CONF} />
              <CopyBlock label="4 · Start & verify" code={SRC_START} />
              <CopyBlock label="5 · Open firewall ports" code={FIREWALL} />
            </div>
          )}

          <div className="neu-pressed rounded-2xl p-4 mt-2 flex items-start gap-3" data-testid="coturn-paste-hint">
            <ShieldCheck className="w-5 h-5 mt-0.5 shrink-0 text-green-500" />
            <div>
              <p className="text-sm font-semibold" style={{ color: "var(--text)" }}>Then paste these into the TURN server fields below:</p>
              <ul className="text-sm text-muted-stitch mt-1.5 space-y-1">
                <li><span className="font-mono-stitch text-primary-stitch">URLs</span> → <span className="font-mono-stitch">turn:YOUR.SERVER.PUBLIC.IP:3478</span></li>
                <li><span className="font-mono-stitch text-primary-stitch">Username</span> → <span className="font-mono-stitch">stitches</span></li>
                <li><span className="font-mono-stitch text-primary-stitch">Credential</span> → the secret you generated above</li>
              </ul>
              <p className="text-xs text-muted-stitch mt-2">After saving, hit <strong>Test connectivity</strong> to confirm the relay is reachable.</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
