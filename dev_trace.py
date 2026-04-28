#!/usr/bin/env python3
# dev_trace.py
# VoidSend Dev Tracer — shows active file, class, and function in real time
# Run alongside the app: python dev_trace.py
# Or as one-shot: python dev_trace.py --once

import sys
import os
import time
import signal
import threading
import argparse
import traceback
import importlib
import inspect
from pathlib import Path
from datetime import datetime

# ── Config ────────────────────────────────────────────────────────────────────

PROJECT_DIR  = Path(__file__).parent
TRACE_LOG    = PROJECT_DIR / ".voidsend_trace.log"
REFRESH_HZ   = 10   # samples per second
WATCH_DIRS   = ["ui", "core", "config", "logs", "raffle_server"]
IGNORE_FUNCS = {
    "_check_versions", "__init_subclass__", "__class_getitem__",
    "_watch", "_on_idle", "_process_messages", "_dispatch_message",
    "compose", "render", "__repr__", "__str__",
}

# ANSI colors
GRN  = "\033[92m"
CYN  = "\033[96m"
YLW  = "\033[93m"
RED  = "\033[91m"
DIM  = "\033[2m"
BLD  = "\033[1m"
MAG  = "\033[95m"
RST  = "\033[0m"
CLR  = "\033[2J\033[H"


# ── Frame analysis ────────────────────────────────────────────────────────────

def is_project_frame(frame) -> bool:
    """Check if a frame belongs to the VoidSend project."""
    filename = frame.f_code.co_filename
    for watch in WATCH_DIRS:
        if f"/{watch}/" in filename or filename.endswith(f"/{watch}.py"):
            return True
    if "voidsend" in filename.lower():
        return True
    return False


def get_class_from_frame(frame) -> str:
    """Extract class name from a frame if inside a method."""
    try:
        local_self = frame.f_locals.get("self")
        if local_self:
            return type(local_self).__name__
        local_cls = frame.f_locals.get("cls")
        if local_cls:
            return local_cls.__name__
    except Exception:
        pass
    return ""


def get_frame_info(frame) -> dict:
    """Extract all useful info from a frame."""
    code     = frame.f_code
    filename = code.co_filename
    try:
        rel = str(Path(filename).relative_to(PROJECT_DIR))
    except ValueError:
        rel = filename

    return {
        "file":    rel,
        "func":    code.co_name,
        "line":    frame.f_lineno,
        "cls":     get_class_from_frame(frame),
        "locals":  {
            k: _safe_repr(v)
            for k, v in frame.f_locals.items()
            if not k.startswith("__") and k not in ("self", "cls")
        },
    }


def _safe_repr(v) -> str:
    try:
        r = repr(v)
        return r[:80] + "..." if len(r) > 80 else r
    except Exception:
        return "<unrepresentable>"


def snapshot_threads() -> list[dict]:
    """
    Capture current frames of all threads.
    Returns list of active project frames per thread.
    """
    results    = []
    all_frames = sys._current_frames()

    for thread in threading.enumerate():
        tid   = thread.ident
        frame = all_frames.get(tid)
        if not frame:
            continue

        # Walk the stack to find project frames
        project_frames = []
        current = frame
        while current:
            if is_project_frame(current):
                info = get_frame_info(current)
                if info["func"] not in IGNORE_FUNCS:
                    project_frames.append(info)
            current = current.f_back

        if project_frames:
            results.append({
                "thread_name": thread.name,
                "thread_id":   tid,
                "frames":      project_frames,
                "top":         project_frames[0],
            })

    return results


# ── Display ───────────────────────────────────────────────────────────────────

def format_location(info: dict) -> str:
    cls  = f"{CYN}{info['cls']}{RST}." if info["cls"] else ""
    func = f"{GRN}{info['func']}{RST}"
    file = f"{DIM}{info['file']}:{info['line']}{RST}"
    return f"{cls}{func}  {file}"


def format_locals(locals_dict: dict, max_items: int = 5) -> str:
    if not locals_dict:
        return ""
    lines = []
    for i, (k, v) in enumerate(locals_dict.items()):
        if i >= max_items:
            lines.append(f"  {DIM}... +{len(locals_dict)-max_items} more{RST}")
            break
        lines.append(f"  {DIM}{k}{RST} = {YLW}{v}{RST}")
    return "\n".join(lines)


def render_snapshot(snapshots: list[dict], show_locals: bool = False) -> str:
    now   = datetime.now().strftime("%H:%M:%S.%f")[:12]
    lines = []

    lines.append(
        f"{BLD}{'─'*60}{RST}\n"
        f"  {MAG}▓▒░ VOIDSEND DEV TRACER ░▒▓{RST}  "
        f"{DIM}{now}{RST}\n"
        f"{BLD}{'─'*60}{RST}"
    )

    if not snapshots:
        lines.append(
            f"\n  {YLW}⚠  No project frames active{RST}\n"
            f"  {DIM}App may be idle or waiting for input{RST}\n"
        )
        return "\n".join(lines)

    for snap in snapshots:
        tname = snap["thread_name"]
        top   = snap["top"]

        lines.append(f"\n  {BLD}Thread:{RST} {DIM}{tname}{RST}")
        lines.append(f"  {BLD}Active:{RST} {format_location(top)}")

        # Show call stack (most recent first)
        if len(snap["frames"]) > 1:
            lines.append(f"  {DIM}Stack (innermost first):{RST}")
            for i, frame in enumerate(snap["frames"][:6]):
                prefix = "  ▶" if i == 0 else "   "
                lines.append(
                    f"  {prefix} {format_location(frame)}"
                )

        # Show locals of top frame
        if show_locals and top.get("locals"):
            lines.append(f"  {DIM}Locals:{RST}")
            lines.append(format_locals(top["locals"]))

    lines.append(f"\n{BLD}{'─'*60}{RST}")
    lines.append(
        f"  {DIM}[q] quit  [l] toggle locals  "
        f"[s] save snapshot  [f] freeze{RST}"
    )

    return "\n".join(lines)


def write_log(content: str):
    """Write snapshot to log file for external viewing."""
    try:
        TRACE_LOG.write_text(content, encoding="utf-8")
    except Exception:
        pass


# ── Modes ─────────────────────────────────────────────────────────────────────

def run_live(show_locals: bool = False, freeze: bool = False):
    """
    Live mode — refreshes every 100ms.
    Attach to the running VoidSend process by importing its modules.
    """
    frozen     = False
    last_snap  = []

    def handle_key():
        nonlocal show_locals, frozen, last_snap
        import termios
        import tty
        fd = sys.stdin.fileno()
        old = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            while True:
                ch = sys.stdin.read(1)
                if ch == "q":
                    os.kill(os.getpid(), signal.SIGINT)
                elif ch == "l":
                    show_locals = not show_locals
                elif ch == "f":
                    frozen = not frozen
                elif ch == "s":
                    _save_snapshot(last_snap)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)

    key_thread = threading.Thread(
        target=handle_key, daemon=True
    )
    key_thread.start()

    try:
        while True:
            if not frozen:
                snaps     = snapshot_threads()
                last_snap = snaps
                output    = render_snapshot(snaps, show_locals)
                write_log(output)
                sys.stdout.write(CLR + output + "\n")
                sys.stdout.flush()
            time.sleep(1.0 / REFRESH_HZ)

    except KeyboardInterrupt:
        print(f"\n{GRN}Tracer stopped.{RST}")
        if TRACE_LOG.exists():
            TRACE_LOG.unlink()


def run_once(show_locals: bool = False):
    """Single snapshot — print and exit."""
    snaps  = snapshot_threads()
    output = render_snapshot(snaps, show_locals)
    print(output)
    write_log(output)


def _save_snapshot(snaps: list[dict]):
    """Save current snapshot to timestamped file."""
    ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = PROJECT_DIR / f".trace_snapshot_{ts}.txt"
    content = render_snapshot(snaps, show_locals=True)
    path.write_text(content, encoding="utf-8")
    sys.stdout.write(
        f"\r  {GRN}✓ Snapshot saved: {path.name}{RST}\n"
    )
    sys.stdout.flush()


# ── Dev.sh integration ────────────────────────────────────────────────────────

def watch_log_mode():
    """
    Passive mode — just watch the .voidsend_trace.log file.
    Use this if you can't run dev_trace.py in the same process.
    """
    print(f"{CYN}Watching {TRACE_LOG}...{RST}")
    print(f"{DIM}Run 'python dev_trace.py' in another tab first{RST}\n")

    last_content = ""
    try:
        while True:
            if TRACE_LOG.exists():
                content = TRACE_LOG.read_text(encoding="utf-8")
                if content != last_content:
                    sys.stdout.write(CLR + content + "\n")
                    sys.stdout.flush()
                    last_content = content
            time.sleep(0.2)
    except KeyboardInterrupt:
        print(f"\n{GRN}Watcher stopped.{RST}")


# ── Entry ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="VoidSend Dev Tracer — see active file/class/function"
    )
    parser.add_argument(
        "--once", "-o",
        action="store_true",
        help="Print one snapshot and exit",
    )
    parser.add_argument(
        "--locals", "-l",
        action="store_true",
        help="Show local variables in active frame",
    )
    parser.add_argument(
        "--watch", "-w",
        action="store_true",
        help="Watch log file written by another tracer instance",
    )
    args = parser.parse_args()

    if args.watch:
        watch_log_mode()
    elif args.once:
        run_once(show_locals=args.locals)
    else:
        run_live(show_locals=args.locals)
