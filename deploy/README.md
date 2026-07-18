# Stitches self-hosted conferencing (LiveKit SFU + coturn TURN)

Stitches ships with peer-to-peer (mesh) WebRTC that works out of the box using public STUN.
For **large meetings** and **guaranteed connectivity behind restrictive/corporate NATs**, run a
LiveKit **SFU** and a coturn **TURN** server. Both are OFF by default and enabled purely by
configuration — no code changes.

## 1. Bring up the servers

```bash
cp deploy/.env.example deploy/.env
# edit deploy/.env — set strong secrets and TURN_PUBLIC_IP to the host's public IP
docker compose -f deploy/docker-compose.yml up -d
```

Open the firewall for:

| Service | Ports |
| --- | --- |
| LiveKit | 7880 (ws/api), 7881/tcp, 50000-60000/udp |
| coturn  | 3478/udp+tcp, 5349/tcp (TLS), 49152-65535/udp (relay) |

Put LiveKit behind TLS (e.g. Caddy/Nginx) so the browser can reach it over `wss://`.

## 2. Point Stitches at them (Admin → Meetings)

**SFU / LiveKit card**
- Enable the toggle
- URL: `wss://your-domain:7880` (or your reverse-proxy URL)
- API key / secret: the `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` from `deploy/.env`

**TURN card**
- URLs: `turn:your-domain:3478` (add `,turns:your-domain:5349` for TLS)
- Username / credential: the `TURN_USERNAME` / `TURN_CREDENTIAL` from `deploy/.env`

Alternatively set them as backend env vars (fallbacks): `LIVEKIT_ENABLED`, `LIVEKIT_URL`,
`LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `TURN_URLS`, `TURN_USERNAME`, `TURN_CREDENTIAL`.

## 3. How Stitches uses it

- `GET /api/rtc/config` returns `iceServers` (STUN + your TURN) and `sfu:{enabled,url}`.
- When SFU is enabled, the call page renders the LiveKit `<VideoConference/>` and mints a
  join token from `POST /api/rtc/sfu-token`. Otherwise it falls back to the built-in P2P room.
- TURN is used automatically by both paths for NAT traversal when direct connections fail.

> The media path is only functional once these servers are reachable with open UDP ports — it
> cannot be exercised inside the managed Emergent preview, which is why it ships gated OFF.
