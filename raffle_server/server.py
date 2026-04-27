# raffle_server/server.py
# VoidSend - Lightweight aiohttp raffle verification server
# Runs locally while raffle is active
# Subscribers visit http://YOUR_IP:PORT/verify to check their ticket

import asyncio
import json
import os
from pathlib import Path
from typing import Optional, Callable

from aiohttp import web

from core.raffle import (
    load_raffle, verify_ticket,
    RaffleConfig, RaffleStatus,
)

VERIFY_HTML = Path(__file__).parent / "verify.html"


class RaffleServer:
    """
    Lightweight HTTP server for raffle ticket verification.
    One instance per active raffle.
    """

    def __init__(
        self,
        raffle_id:   str,
        port:        int = 8080,
        on_winner:   Optional[Callable[[dict], None]] = None,
        on_verify:   Optional[Callable[[dict], None]] = None,
    ):
        self.raffle_id = raffle_id
        self.port      = port
        self.on_winner = on_winner   # fired when a winner verifies
        self.on_verify = on_verify   # fired on any verification attempt
        self._app:     Optional[web.Application] = None
        self._runner:  Optional[web.AppRunner]   = None
        self._site:    Optional[web.TCPSite]     = None
        self.running   = False

    async def start(self):
        """Start the verification server."""
        self._app = web.Application()
        self._app.router.add_get("/",        self._handle_index)
        self._app.router.add_get("/verify",  self._handle_verify_page)
        self._app.router.add_post("/verify", self._handle_verify_submit)
        self._app.router.add_get("/status",  self._handle_status)

        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(
            self._runner, "0.0.0.0", self.port
        )
        await self._site.start()
        self.running = True

    async def stop(self):
        """Gracefully stop the server."""
        if self._runner:
            await self._runner.cleanup()
        self.running = False

    # ── Routes ────────────────────────────────────────────────────────────────

    async def _handle_index(self, request: web.Request) -> web.Response:
        raise web.HTTPFound("/verify")

    async def _handle_verify_page(
        self, request: web.Request
    ) -> web.Response:
        """Serve the verification HTML page."""
        raffle = load_raffle(self.raffle_id)
        if not raffle:
            return web.Response(
                text="Raffle not found.", content_type="text/plain"
            )

        if VERIFY_HTML.exists():
            html = VERIFY_HTML.read_text(encoding="utf-8")
            # Inject raffle details
            html = html.replace("{{RAFFLE_NAME}}", raffle.name)
            html = html.replace("{{RAFFLE_PRIZE}}", raffle.prize)
            html = html.replace(
                "{{TICKET_LENGTH}}", str(raffle.ticket_length)
            )
            expiry = raffle.expiry_date or "No expiry"
            html = html.replace("{{EXPIRY_DATE}}", expiry)
            html = html.replace(
                "{{RAFFLE_MESSAGE}}",
                raffle.message or "Enter your ticket number below."
            )
        else:
            html = _fallback_html(raffle)

        return web.Response(text=html, content_type="text/html")

    async def _handle_verify_submit(
        self, request: web.Request
    ) -> web.Response:
        """Handle ticket submission."""
        raffle = load_raffle(self.raffle_id)
        if not raffle:
            return web.json_response(
                {"error": "Raffle not found"}, status=404
            )

        if raffle.status == RaffleStatus.CLOSED:
            return web.json_response(
                {"error": "This raffle is now closed."},
                status=403,
            )

        try:
            data   = await request.json()
            ticket = str(data.get("ticket", "")).strip()
        except Exception:
            try:
                post   = await request.post()
                ticket = str(post.get("ticket", "")).strip()
            except Exception:
                ticket = ""

        if not ticket:
            return web.json_response(
                {"error": "No ticket number provided."}, status=400
            )

        result = verify_ticket(raffle, ticket)

        # Fire callbacks
        if self.on_verify:
            self.on_verify(result)
        if result.get("winner") and self.on_winner:
            self.on_winner(result)

        return web.json_response(result)

    async def _handle_status(
        self, request: web.Request
    ) -> web.Response:
        """Simple status endpoint."""
        raffle = load_raffle(self.raffle_id)
        if not raffle:
            return web.json_response({"status": "not_found"})
        from core.raffle import raffle_stats
        return web.json_response({
            "raffle_id": raffle.raffle_id,
            "name":      raffle.name,
            "status":    raffle.status.value,
            "stats":     raffle_stats(raffle),
        })


# ── Fallback HTML ─────────────────────────────────────────────────────────────

def _fallback_html(raffle: RaffleConfig) -> str:
    """Minimal fallback if verify.html is missing."""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><title>{raffle.name}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{font-family:sans-serif;max-width:480px;margin:40px auto;padding:20px;}}
input{{width:100%;padding:12px;font-size:18px;text-align:center;
letter-spacing:4px;border:2px solid #ccc;border-radius:6px;}}
button{{width:100%;padding:14px;background:#2563eb;color:#fff;
border:none;border-radius:6px;font-size:16px;margin-top:12px;cursor:pointer;}}
#result{{margin-top:20px;padding:16px;border-radius:6px;display:none;}}
</style></head>
<body>
<h2>{raffle.name}</h2>
<p>Prize: <strong>{raffle.prize}</strong></p>
<input id="ticket" placeholder="Enter your ticket number"
  maxlength="{raffle.ticket_length}">
<button onclick="verify()">Check My Ticket</button>
<div id="result"></div>
<script>
async function verify(){{
  const t=document.getElementById('ticket').value.trim();
  if(!t)return;
  const r=await fetch('/verify',{{method:'POST',
    headers:{{'Content-Type':'application/json'}},
    body:JSON.stringify({{ticket:t}})}});
  const d=await r.json();
  const el=document.getElementById('result');
  el.style.display='block';
  if(d.winner){{
    el.style.background='#d1fae5';
    el.style.border='2px solid #10b981';
    el.innerHTML='<h3>🎉 You Won!</h3><p>'+d.message+'</p>';
  }}else if(d.valid){{
    el.style.background='#fee2e2';
    el.style.border='2px solid #ef4444';
    el.innerHTML='<p>'+d.message+'</p>';
  }}else{{
    el.style.background='#fef3c7';
    el.style.border='2px solid #f59e0b';
    el.innerHTML='<p>'+d.message+'</p>';
  }}
}}
</script>
</body></html>"""


# ── Server manager (singleton per raffle) ────────────────────────────────────

_active_servers: dict[str, RaffleServer] = {}


async def start_raffle_server(
    raffle_id:  str,
    port:       int = 8080,
    on_winner:  Optional[Callable] = None,
    on_verify:  Optional[Callable] = None,
) -> RaffleServer:
    """Start a raffle server. Stops existing server on same port first."""
    # Stop any existing server on this port
    for rid, srv in list(_active_servers.items()):
        if srv.port == port:
            await srv.stop()
            del _active_servers[rid]

    server = RaffleServer(
        raffle_id = raffle_id,
        port      = port,
        on_winner = on_winner,
        on_verify = on_verify,
    )
    await server.start()
    _active_servers[raffle_id] = server
    return server


async def stop_raffle_server(raffle_id: str):
    """Stop a specific raffle server."""
    if raffle_id in _active_servers:
        await _active_servers[raffle_id].stop()
        del _active_servers[raffle_id]


def get_active_server(raffle_id: str) -> Optional[RaffleServer]:
    return _active_servers.get(raffle_id)
