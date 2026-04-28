# raffle_server/server.py
# VoidSend - Raffle verification server
# Added: entry tracking, CORS for GitHub Pages, tunnel URL injection

import asyncio
import json
import time
from pathlib import Path
from typing import Optional, Callable

from aiohttp import web
from aiohttp.web_middlewares import middleware

from core.raffle import (
    load_raffle, verify_ticket,
    RaffleConfig, RaffleStatus,
)

VERIFY_HTML   = Path(__file__).parent / "verify.html"
ENTRIES_LOG   = Path.home() / ".voidsend" / "raffle_entries.json"


# ── Entry tracking ────────────────────────────────────────────────────────────

def _load_entries(raffle_id: str) -> list[dict]:
    if not ENTRIES_LOG.exists():
        return []
    try:
        data = json.loads(ENTRIES_LOG.read_text())
        return [e for e in data if e.get("raffle_id") == raffle_id]
    except Exception:
        return []


def _save_entry(raffle_id: str, entry: dict):
    ENTRIES_LOG.parent.mkdir(parents=True, exist_ok=True)
    all_entries = []
    if ENTRIES_LOG.exists():
        try:
            all_entries = json.loads(ENTRIES_LOG.read_text())
        except Exception:
            all_entries = []

    all_entries.append({
        "raffle_id":  raffle_id,
        "timestamp":  time.strftime("%Y-%m-%d %H:%M:%S"),
        "unix_time":  time.time(),
        **entry,
    })

    ENTRIES_LOG.write_text(
        json.dumps(all_entries, indent=2),
        encoding="utf-8"
    )


def get_all_entries(raffle_id: str) -> list[dict]:
    return _load_entries(raffle_id)


def clear_entries(raffle_id: str):
    if not ENTRIES_LOG.exists():
        return
    try:
        data = json.loads(ENTRIES_LOG.read_text())
        data = [e for e in data if e.get("raffle_id") != raffle_id]
        ENTRIES_LOG.write_text(json.dumps(data, indent=2))
    except Exception:
        pass


# ── CORS middleware ───────────────────────────────────────────────────────────

@middleware
async def cors_middleware(request: web.Request, handler):
    """Allow GitHub Pages origin to POST to local server."""
    if request.method == "OPTIONS":
        return web.Response(
            headers={
                "Access-Control-Allow-Origin":  "*",
                "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )
    resp = await handler(request)
    resp.headers["Access-Control-Allow-Origin"]  = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


# ── Server ────────────────────────────────────────────────────────────────────

class RaffleServer:

    def __init__(
        self,
        raffle_id:  str,
        port:       int = 8080,
        verify_url: str = "",
        on_winner:  Optional[Callable[[dict], None]] = None,
        on_verify:  Optional[Callable[[dict], None]] = None,
        on_entry:   Optional[Callable[[dict], None]] = None,
    ):
        self.raffle_id  = raffle_id
        self.port       = port
        self.verify_url = verify_url  # public URL (ngrok or LAN)
        self.on_winner  = on_winner
        self.on_verify  = on_verify
        self.on_entry   = on_entry    # fires on EVERY attempt
        self._runner: Optional[web.AppRunner]  = None
        self._site:   Optional[web.TCPSite]    = None
        self.running    = False

    async def start(self):
        app = web.Application(middlewares=[cors_middleware])
        app.router.add_get("/",        self._handle_index)
        app.router.add_get("/verify",  self._handle_verify_page)
        app.router.add_post("/verify", self._handle_verify_submit)
        app.router.add_get("/status",  self._handle_status)
        app.router.add_get("/entries", self._handle_entries)
        app.router.add_options("/verify", self._handle_options)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, "0.0.0.0", self.port)
        await self._site.start()
        self.running = True

    async def stop(self):
        if self._runner:
            await self._runner.cleanup()
        self.running = False

    # ── Routes ────────────────────────────────────────────────────────────────

    async def _handle_options(self, req: web.Request) -> web.Response:
        return web.Response(status=200)

    async def _handle_index(self, req: web.Request) -> web.Response:
        raise web.HTTPFound("/verify")

    async def _handle_verify_page(
        self, req: web.Request
    ) -> web.Response:
        raffle = load_raffle(self.raffle_id)
        if not raffle:
            return web.Response(
                text="Raffle not found.", content_type="text/plain"
            )

        if VERIFY_HTML.exists():
            html = VERIFY_HTML.read_text(encoding="utf-8")
            # Inject config
            replacements = {
                "RAFFLE_NAME_PLACEHOLDER":   raffle.name,
                "RAFFLE_PRIZE_PLACEHOLDER":  raffle.prize,
                "TICKET_LENGTH_PLACEHOLDER": str(raffle.ticket_length),
                "TICKET_PLACEHOLDER":        "0" * raffle.ticket_length,
                "VERIFY_URL_PLACEHOLDER":    (
                    self.verify_url
                    or f"http://localhost:{self.port}/verify"
                ),
                "RAFFLE_ID_PLACEHOLDER":     raffle.raffle_id,
                "EXPIRY_PLACEHOLDER":        raffle.expiry_date or "No expiry",
                "RAFFLE_MESSAGE_PLACEHOLDER": raffle.message or "",
            }
            for k, v in replacements.items():
                html = html.replace(k, v)
        else:
            html = f"<h1>{raffle.name}</h1><p>verify.html missing</p>"

        return web.Response(text=html, content_type="text/html")

    async def _handle_verify_submit(
        self, req: web.Request
    ) -> web.Response:
        raffle = load_raffle(self.raffle_id)
        if not raffle:
            return web.json_response(
                {"error": "Raffle not found"}, status=404
            )

        if raffle.status == RaffleStatus.CLOSED:
            return web.json_response(
                {"error": "This raffle is closed."}, status=403
            )

        # Parse body
        try:
            data   = await req.json()
            ticket = str(data.get("ticket", "")).strip()
        except Exception:
            try:
                post   = await req.post()
                ticket = str(post.get("ticket", "")).strip()
            except Exception:
                ticket = ""

        if not ticket:
            return web.json_response(
                {"error": "No ticket provided."}, status=400
            )

        # Get requester IP
        ip = (
            req.headers.get("X-Forwarded-For", "")
            or req.remote
            or "unknown"
        )

        result = verify_ticket(raffle, ticket)

        # Build entry log
        entry = {
            "ticket":    ticket,
            "valid":     result.get("valid", False),
            "winner":    result.get("winner", False),
            "email":     result.get("email", ""),
            "name":      result.get("name", ""),
            "ip":        ip,
            "message":   result.get("message", ""),
        }

        # Persist entry
        _save_entry(self.raffle_id, entry)

        # Fire callbacks
        if self.on_entry:
            self.on_entry(entry)
        if self.on_verify:
            self.on_verify(result)
        if result.get("winner") and self.on_winner:
            self.on_winner({**result, **entry})

        return web.json_response(result)

    async def _handle_status(
        self, req: web.Request
    ) -> web.Response:
        raffle = load_raffle(self.raffle_id)
        if not raffle:
            return web.json_response({"status": "not_found"})
        from core.raffle import raffle_stats
        entries = get_all_entries(self.raffle_id)
        return web.json_response({
            "raffle_id":   raffle.raffle_id,
            "name":        raffle.name,
            "status":      raffle.status.value,
            "stats":       raffle_stats(raffle),
            "entry_count": len(entries),
            "verify_url":  self.verify_url,
        })

    async def _handle_entries(
        self, req: web.Request
    ) -> web.Response:
        """Return all entry attempts for this raffle."""
        entries = get_all_entries(self.raffle_id)
        return web.json_response(entries)


# ── Server manager ────────────────────────────────────────────────────────────

_active_servers: dict[str, RaffleServer] = {}


async def start_raffle_server(
    raffle_id:  str,
    port:       int = 8080,
    verify_url: str = "",
    on_winner:  Optional[Callable] = None,
    on_verify:  Optional[Callable] = None,
    on_entry:   Optional[Callable] = None,
) -> RaffleServer:
    # Stop any existing server on this port
    for rid, srv in list(_active_servers.items()):
        if srv.port == port:
            await srv.stop()
            del _active_servers[rid]

    server = RaffleServer(
        raffle_id  = raffle_id,
        port       = port,
        verify_url = verify_url,
        on_winner  = on_winner,
        on_verify  = on_verify,
        on_entry   = on_entry,
    )
    await server.start()
    _active_servers[raffle_id] = server
    return server


async def stop_raffle_server(raffle_id: str):
    if raffle_id in _active_servers:
        await _active_servers[raffle_id].stop()
        del _active_servers[raffle_id]


def get_active_server(raffle_id: str) -> Optional[RaffleServer]:
    return _active_servers.get(raffle_id)
