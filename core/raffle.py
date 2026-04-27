# core/raffle.py
# VoidSend - Raffle engine
# Generates tickets, manages winners, persists raffle state

import json
import os
import random
import string
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Optional

RAFFLES_DIR = Path.home() / ".voidsend" / "raffles"


class RaffleStatus(Enum):
    DRAFT    = "draft"
    ACTIVE   = "active"
    CLOSED   = "closed"


@dataclass
class RaffleEntry:
    """A single subscriber's raffle ticket."""
    email:       str
    name:        str
    ticket:      str
    is_winner:   bool  = False
    verified_at: Optional[float] = None
    verified:    bool  = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "RaffleEntry":
        return cls(**{
            k: v for k, v in d.items()
            if k in cls.__dataclass_fields__
        })


@dataclass
class RaffleConfig:
    """Full raffle configuration and state."""
    raffle_id:      str
    name:           str
    prize:          str
    ticket_length:  int              # 4, 6, or 9
    winner_count:   int              # how many winners
    status:         RaffleStatus
    server_port:    int              = 8080
    expiry_date:    Optional[str]    = None   # "YYYY-MM-DD"
    created_at:     float            = field(default_factory=time.time)
    entries:        list             = field(default_factory=list)
    winning_tickets: list[str]       = field(default_factory=list)
    verify_url:     str              = ""
    message:        str              = ""     # custom raffle message

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "RaffleConfig":
        entries = [RaffleEntry.from_dict(e) for e in d.get("entries", [])]
        return cls(
            raffle_id       = d["raffle_id"],
            name            = d["name"],
            prize           = d["prize"],
            ticket_length   = d["ticket_length"],
            winner_count    = d["winner_count"],
            status          = RaffleStatus(d.get("status", "draft")),
            server_port     = d.get("server_port", 8080),
            expiry_date     = d.get("expiry_date"),
            created_at      = d.get("created_at", time.time()),
            entries         = entries,
            winning_tickets = d.get("winning_tickets", []),
            verify_url      = d.get("verify_url", ""),
            message         = d.get("message", ""),
        )


# ── Ticket generation ─────────────────────────────────────────────────────────

def _generate_ticket(length: int, existing: set[str]) -> str:
    """Generate a unique numeric ticket of given length."""
    while True:
        ticket = "".join(random.choices(string.digits, k=length))
        # Avoid leading zeros and duplicates
        if ticket[0] != "0" and ticket not in existing:
            return ticket


def generate_tickets(
    subscribers: list[dict],  # [{"email": ..., "name": ...}]
    ticket_length: int,
    winner_count: int,
) -> RaffleConfig:
    """
    Generate a new raffle with tickets for all subscribers.
    Randomly pre-selects winners.
    """
    raffle_id = _make_raffle_id()
    entries   = []
    used      = set()

    for sub in subscribers:
        ticket = _generate_ticket(ticket_length, used)
        used.add(ticket)
        entries.append(RaffleEntry(
            email  = sub["email"],
            name   = sub.get("name", ""),
            ticket = ticket,
        ))

    # Pre-select winners randomly
    winner_count   = min(winner_count, len(entries))
    winning_idxs   = random.sample(range(len(entries)), winner_count)
    winning_tickets = []
    for idx in winning_idxs:
        entries[idx].is_winner = True
        winning_tickets.append(entries[idx].ticket)

    return RaffleConfig(
        raffle_id       = raffle_id,
        name            = "",
        prize           = "",
        ticket_length   = ticket_length,
        winner_count    = winner_count,
        status          = RaffleStatus.DRAFT,
        entries         = entries,
        winning_tickets = winning_tickets,
    )


def _make_raffle_id() -> str:
    import uuid
    return str(uuid.uuid4())[:8].upper()


# ── Verification ──────────────────────────────────────────────────────────────

def verify_ticket(
    raffle: RaffleConfig,
    ticket: str,
) -> dict:
    """
    Check if a ticket is valid and a winner.
    Returns: {valid, winner, prize, message, email}
    """
    ticket = ticket.strip()

    # Find entry
    entry = next(
        (e for e in raffle.entries if e.ticket == ticket),
        None
    )

    if not entry:
        return {
            "valid":   False,
            "winner":  False,
            "prize":   "",
            "message": "Ticket not found. Please check your number.",
            "email":   "",
        }

    # Mark as verified
    entry.verified    = True
    entry.verified_at = time.time()
    save_raffle(raffle)

    if entry.is_winner:
        return {
            "valid":   True,
            "winner":  True,
            "prize":   raffle.prize,
            "message": f"🎉 Congratulations! You won: {raffle.prize}",
            "email":   entry.email,
            "name":    entry.name,
        }
    else:
        return {
            "valid":   True,
            "winner":  False,
            "prize":   "",
            "message": "Thank you for participating! Better luck next time.",
            "email":   entry.email,
            "name":    entry.name,
        }


def get_entry_by_ticket(
    raffle: RaffleConfig,
    ticket: str,
) -> Optional[RaffleEntry]:
    return next(
        (e for e in raffle.entries if e.ticket == ticket),
        None
    )


# ── Persistence ───────────────────────────────────────────────────────────────

def save_raffle(raffle: RaffleConfig) -> Path:
    RAFFLES_DIR.mkdir(parents=True, exist_ok=True)
    path = RAFFLES_DIR / f"{raffle.raffle_id}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(raffle.to_dict(), f, indent=2)
    return path


def load_raffle(raffle_id: str) -> Optional[RaffleConfig]:
    path = RAFFLES_DIR / f"{raffle_id}.json"
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return RaffleConfig.from_dict(json.load(f))


def list_raffles() -> list[RaffleConfig]:
    RAFFLES_DIR.mkdir(parents=True, exist_ok=True)
    raffles = []
    for p in sorted(RAFFLES_DIR.glob("*.json"), reverse=True):
        try:
            with open(p, "r", encoding="utf-8") as f:
                raffles.append(RaffleConfig.from_dict(json.load(f)))
        except Exception:
            continue
    return raffles


def delete_raffle(raffle_id: str) -> bool:
    path = RAFFLES_DIR / f"{raffle_id}.json"
    if path.exists():
        path.unlink()
        return True
    return False


# ── Stats ─────────────────────────────────────────────────────────────────────

def raffle_stats(raffle: RaffleConfig) -> dict:
    total     = len(raffle.entries)
    verified  = sum(1 for e in raffle.entries if e.verified)
    winners   = sum(1 for e in raffle.entries if e.is_winner)
    claimed   = sum(
        1 for e in raffle.entries if e.is_winner and e.verified
    )
    return {
        "total":        total,
        "verified":     verified,
        "winners":      winners,
        "claimed":      claimed,
        "unclaimed":    winners - claimed,
        "participation": f"{verified/total*100:.1f}%" if total else "0%",
    }


# ── Local IP helper ───────────────────────────────────────────────────────────

def get_local_ip() -> str:
    """Get device local IP for verify URL."""
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"
