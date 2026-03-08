# ╔══════════════════════════════════════════════════════════════════════╗
# ║   ⚡ GADGET PREMIUM HOST  v3.0  ·  utils.py                         ║
# ╚══════════════════════════════════════════════════════════════════════╝

from __future__ import annotations

import ast
import os
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import config

# ─────────────────────────────────────────────────────────────────────
# TEXT FORMATTING
# ─────────────────────────────────────────────────────────────────────

def bar(cur: int | float, total: int | float, length: int = 12, fill: str = "█", empty: str = "░") -> str:
    if total <= 0:
        total = 1
    pct   = min(cur / total, 1.0)
    done  = int(length * pct)
    return fill * done + empty * (length - done)


def pbar(cur: int | float, total: int | float, length: int = 10) -> str:
    """Returns [████░░░░░░] style string."""
    return f"[{bar(cur, total, length)}]"


def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"


def fmt_uptime(secs: float) -> str:
    secs = int(secs)
    d, r = divmod(secs, 86400)
    h, r = divmod(r, 3600)
    m, s = divmod(r, 60)
    parts = []
    if d: parts.append(f"{d}d")
    if h: parts.append(f"{h}h")
    if m: parts.append(f"{m}m")
    parts.append(f"{s}s")
    return " ".join(parts)


def fmt_ts(ts: Optional[str], fmt: str = "%Y-%m-%d %H:%M") -> str:
    if not ts:
        return "Never"
    try:
        return datetime.fromisoformat(ts).strftime(fmt)
    except Exception:
        return str(ts)[:16]


def plan_label(plan: str) -> str:
    return config.PLANS.get(plan, config.PLANS["free"])["label"]


def plan_emoji(plan: str) -> str:
    return config.PLANS.get(plan, config.PLANS["free"])["emoji"]


def plan_slots(plan: str) -> int:
    return config.PLANS.get(plan, config.PLANS["free"])["slots"]


def status_icon(status: str) -> str:
    return {"running": "🟢", "stopped": "🔴", "error": "🟡", "deleted": "⬛"}.get(status, "⚪")


# ─────────────────────────────────────────────────────────────────────
# SECTION BOXES
# ─────────────────────────────────────────────────────────────────────

def box(title: str, width: int = 32) -> str:
    pad = max(0, width - len(title) - 4)
    left  = pad // 2
    right = pad - left
    return (
        f"╔{'═' * (width)}╗\n"
        f"║{' ' * left}  {title}  {' ' * right}║\n"
        f"╚{'═' * (width)}╝"
    )


def divider(width: int = 33) -> str:
    return "━" * width


# ─────────────────────────────────────────────────────────────────────
# SYNTAX GUARD
# ─────────────────────────────────────────────────────────────────────

def syntax_check(source: str) -> tuple[bool, str]:
    """
    Parses Python source with ast.
    Returns (ok, error_html).
    """
    try:
        tree = ast.parse(source)
        # Extra: warn on dangerous top-level calls
        warnings = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                if isinstance(func, ast.Attribute) and func.attr in ("system", "popen"):
                    warnings.append(f"⚠️ Possible shell call detected: <code>{func.attr}</code>")
        warn_block = ("\n\n" + "\n".join(warnings)) if warnings else ""
        return True, warn_block
    except SyntaxError as e:
        snippet = (e.text or "").rstrip()
        pointer = " " * (e.offset - 1) + "^" if e.offset else ""
        return False, (
            "🛡️ <b>Syntax Guard: REJECTED</b>\n\n"
            f"🔍 <b>Line {e.lineno}:</b> <code>{e.msg}</code>\n"
            f"<pre>{snippet}\n{pointer}</pre>\n"
            "<i>Fix the error and re-upload.</i>"
        )
    except Exception as e:
        return False, f"⚠️ <b>Parse Error:</b> <code>{e}</code>"


# ─────────────────────────────────────────────────────────────────────
# MAINTENANCE
# ─────────────────────────────────────────────────────────────────────

def is_maintenance() -> bool:
    return Path(config.MAINTENANCE_FILE).exists()


def set_maintenance(on: bool) -> None:
    p = Path(config.MAINTENANCE_FILE)
    p.parent.mkdir(parents=True, exist_ok=True)
    if on:
        p.write_text(datetime.now().isoformat())
    else:
        p.unlink(missing_ok=True)


def maintenance_since() -> Optional[str]:
    p = Path(config.MAINTENANCE_FILE)
    if not p.exists():
        return None
    try:
        return p.read_text().strip()
    except Exception:
        return "unknown"


# ─────────────────────────────────────────────────────────────────────
# ADMIN CHECK
# ─────────────────────────────────────────────────────────────────────

def is_owner(uid: int) -> bool:
    return uid == config.OWNER_ID


def is_admin(uid: int) -> bool:
    return uid == config.OWNER_ID or uid in config.CO_ADMINS


# ─────────────────────────────────────────────────────────────────────
# SAFE FILENAME
# ─────────────────────────────────────────────────────────────────────

def safe_name(name: str) -> str:
    import re
    return re.sub(r"[^\w\-_.]", "_", name)


# ─────────────────────────────────────────────────────────────────────
# RATE LIMITER (in-memory, per user)
# ─────────────────────────────────────────────────────────────────────

_cooldowns: dict[int, float] = {}


def is_rate_limited(uid: int, cooldown: float = config.USER_CMD_COOLDOWN) -> bool:
    now = time.time()
    last = _cooldowns.get(uid, 0)
    if now - last < cooldown:
        return True
    _cooldowns[uid] = now
    return False


# ─────────────────────────────────────────────────────────────────────
# DASHBOARD TEXT BUILDER
# ─────────────────────────────────────────────────────────────────────

def build_dashboard(uid: int, full_name: str) -> str:
    import database as db
    row      = db.get_user(uid)
    used, mx = db.get_slot_counts(uid)
    refs     = db.referral_count(uid)
    plan     = row["plan"] if row else "free"
    coins    = row["coins"] if row else 0
    streak   = row["daily_streak"] if row else 0
    bots_row = db.get_user_bots(uid)
    running  = sum(1 for b in bots_row if b["status"] == "running")
    slot_bar = pbar(used, mx)

    lines = [
        "╔═══════════════════════════════╗",
        f"║   ⚡  <b>{config.BOT_NAME}</b>",
        f"║       v{config.BOT_VERSION}  ·  Premium Hosting",
        "╚═══════════════════════════════╝",
        "",
        f"👋  <b>Hello, {full_name}!</b>",
        "",
        divider(),
        f"📋  Plan:       {plan_label(plan)}",
        f"🤖  Slots:      {slot_bar} <code>{used}/{mx}</code>",
        f"🟢  Running:    <code>{running}</code>  bot(s)",
        f"🪙  Coins:      <code>{coins:,}</code>",
        f"🔥  Streak:     <code>{streak}</code> day(s)",
        f"🔗  Referrals:  <code>{refs}</code> friends",
        divider(),
        "<i>Deploy · Manage · Earn  🚀</i>",
    ]
    return "\n".join(lines)
