# raffle_server/tunnel.py
# VoidSend - ngrok tunnel manager
# Opens a public HTTPS tunnel to the local raffle server
# Requires: pip install pyngrok

from pathlib import Path
from typing import Optional
import asyncio
import time

_active_tunnel = None
_tunnel_url    = None


def is_ngrok_available() -> bool:
    """Check if pyngrok is installed."""
    try:
        import pyngrok
        return True
    except ImportError:
        return False


def get_tunnel_url() -> Optional[str]:
    """Return current active tunnel URL or None."""
    return _tunnel_url


async def start_tunnel(
    port:       int = 8080,
    auth_token: Optional[str] = None,
) -> tuple[bool, str]:
    """
    Start an ngrok tunnel to the given port.
    Returns (success, url_or_error_message).

    auth_token: optional ngrok auth token for longer sessions.
    Free ngrok sessions expire after ~2hrs without token.
    Get token free at: https://dashboard.ngrok.com
    """
    global _active_tunnel, _tunnel_url

    if not is_ngrok_available():
        return False, (
            "pyngrok not installed. Run: pip install pyngrok"
        )

    try:
        from pyngrok import ngrok, conf

        # Set auth token if provided
        if auth_token:
            conf.get_default().auth_token = auth_token

        # Run in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()

        def _open():
            return ngrok.connect(port, "http")

        tunnel = await loop.run_in_executor(None, _open)

        _active_tunnel = tunnel
        _tunnel_url    = tunnel.public_url

        # Force HTTPS
        if _tunnel_url.startswith("http://"):
            _tunnel_url = "https://" + _tunnel_url[7:]

        return True, _tunnel_url

    except Exception as e:
        return False, f"Tunnel error: {e}"


async def stop_tunnel():
    """Stop the active ngrok tunnel."""
    global _active_tunnel, _tunnel_url
    if not _active_tunnel:
        return
    try:
        from pyngrok import ngrok
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: ngrok.disconnect(_active_tunnel.public_url)
        )
    except Exception:
        pass
    finally:
        _active_tunnel = None
        _tunnel_url    = None


def get_tunnel_status() -> dict:
    """Return current tunnel status info."""
    return {
        "active":    _active_tunnel is not None,
        "url":       _tunnel_url,
        "ngrok_ok":  is_ngrok_available(),
    }
