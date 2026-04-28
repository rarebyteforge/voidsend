# raffle_server/github_pages.py
# VoidSend - GitHub Pages deployer
# Deploys verify.html to GitHub Pages with raffle config injected
# Requires: pip install httpx

import base64
import json
import time
from pathlib import Path
from typing import Optional
import httpx

VERIFY_HTML = Path(__file__).parent / "verify.html"
PAGES_BRANCH = "gh-pages"


def _b64(content: str) -> str:
    return base64.b64encode(content.encode()).decode()


def _inject_config(
    html:         str,
    raffle_name:  str,
    raffle_prize: str,
    ticket_len:   int,
    verify_url:   str,
    raffle_id:    str,
    expiry:       str = "",
) -> str:
    """Replace all placeholders in verify.html with real values."""
    placeholder = "0" * ticket_len
    expiry_str  = expiry if expiry else "No expiry"

    replacements = {
        "RAFFLE_NAME_PLACEHOLDER":   raffle_name,
        "RAFFLE_PRIZE_PLACEHOLDER":  raffle_prize,
        "TICKET_LENGTH_PLACEHOLDER": str(ticket_len),
        "TICKET_PLACEHOLDER":        placeholder,
        "VERIFY_URL_PLACEHOLDER":    verify_url,
        "RAFFLE_ID_PLACEHOLDER":     raffle_id,
        "EXPIRY_PLACEHOLDER":        expiry_str,
    }
    for key, val in replacements.items():
        html = html.replace(key, val)
    return html


async def deploy_to_github_pages(
    github_token: str,
    repo:         str,          # e.g. "rarebyteforge/voidsend"
    raffle_name:  str,
    raffle_prize: str,
    ticket_len:   int,
    verify_url:   str,
    raffle_id:    str,
    expiry:       str = "",
    path:         str = "raffle/index.html",
) -> tuple[bool, str]:
    """
    Deploy raffle verify page to GitHub Pages.
    Returns (success, page_url_or_error).

    Setup required (one time):
    1. Go to your repo Settings → Pages
    2. Set Source to 'Deploy from branch'
    3. Set Branch to 'gh-pages' / root
    4. Generate token at github.com/settings/tokens
       with 'repo' and 'pages' scopes
    """
    if not VERIFY_HTML.exists():
        return False, "verify.html not found"

    html    = VERIFY_HTML.read_text(encoding="utf-8")
    content = _inject_config(
        html, raffle_name, raffle_prize,
        ticket_len, verify_url, raffle_id, expiry
    )

    headers = {
        "Authorization": f"token {github_token}",
        "Accept":        "application/vnd.github.v3+json",
        "Content-Type":  "application/json",
    }

    base_url = f"https://api.github.com/repos/{repo}/contents/{path}"

    try:
        async with httpx.AsyncClient(timeout=30) as client:

            # Check if file already exists (need SHA for update)
            sha = None
            check = await client.get(
                base_url,
                headers=headers,
                params={"ref": PAGES_BRANCH},
            )
            if check.status_code == 200:
                sha = check.json().get("sha")

            # Build commit payload
            payload: dict = {
                "message": (
                    f"Deploy raffle: {raffle_name} "
                    f"[{time.strftime('%Y-%m-%d %H:%M')}]"
                ),
                "content": _b64(content),
                "branch":  PAGES_BRANCH,
            }
            if sha:
                payload["sha"] = sha

            # Push to GitHub
            resp = await client.put(
                base_url,
                headers=headers,
                content=json.dumps(payload),
            )

            if resp.status_code in (200, 201):
                owner, repo_name = repo.split("/")
                page_url = (
                    f"https://{owner}.github.io"
                    f"/{repo_name}/{path}"
                )
                return True, page_url
            else:
                err = resp.json().get("message", resp.text[:200])
                return False, f"GitHub API error: {err}"

    except httpx.ConnectError:
        return False, (
            "No internet connection — "
            "GitHub Pages deploy requires internet"
        )
    except Exception as e:
        return False, f"Deploy error: {e}"


async def get_pages_url(
    github_token: str,
    repo:         str,
) -> Optional[str]:
    """Get the GitHub Pages base URL for a repo."""
    headers = {
        "Authorization": f"token {github_token}",
        "Accept":        "application/vnd.github.v3+json",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{repo}/pages",
                headers=headers,
            )
            if resp.status_code == 200:
                return resp.json().get("html_url")
    except Exception:
        pass
    return None
