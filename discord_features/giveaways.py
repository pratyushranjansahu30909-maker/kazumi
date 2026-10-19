# -*- coding: utf-8 -*-
"""
🌸 Kazumi Secure, Fair, and Automated Giveaway System
Implements:
- Mode A (Claim Deadline Enabled): Winner must claim before countdown expires, or
  automatic replacement winner reroll selects next eligible participant with a fresh deadline.
- Mode B (Claim Deadline Disabled): Winner claims without automatic expiration; manual reroll if declined.
- Cryptographically secure random selection via Python's `secrets.SystemRandom`.
- Entrant deduplication, bot exclusion, and role/membership eligibility verification.
- Transactional state transitions: DRAFT -> ACTIVE -> CLOSED -> DRAWING -> AWAITING_CLAIM -> CLAIMED / EXPIRED -> COMPLETED.
- Append-only hash-chained audit ledger with SHA-256 tamper verification.
- Interactive claim button (`GiveawayClaimView`) and fairness report generation.
"""

import os
import re
import json
import time
import secrets
import hashlib
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from discord_features.database import get_feature_db, FeatureDatabase

logger = logging.getLogger("KazumiGiveaways")
sys_random = secrets.SystemRandom()


class GiveawayState(str, Enum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    DRAWING = "DRAWING"
    CLAIM_PENDING = "CLAIM_PENDING"
    AWAITING_CLAIM = "AWAITING_CLAIM"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_ELIGIBLE_ENTRANTS = "NO_ELIGIBLE_ENTRANTS"
    EXPIRED = "EXPIRED"
    # Backward compatibility aliases
    CLOSED = "COMPLETED"
    CLAIMED = "COMPLETED"
    REROLLING = "DRAWING"


def parse_duration(duration_str: str) -> Optional[float]:
    """
    Parses duration strings into seconds.
    Supports:
    - 30s, 30 sec, 30 seconds
    - 10m, 10 min, 10 minutes
    - 2h, 2 hr, 2 hours
    - 1d, 1 day, 1 days
    - 1w, 1 week, 1 weeks
    Also tolerates leading 'for' (e.g. 'for 2h', 'for 15 minutes').
    Returns float seconds or None.
    """
    if not duration_str:
        return None
    raw = str(duration_str).strip().lower()
    raw = re.sub(r"^(?:for\s+)+", "", raw).strip()
    match = re.match(r"^(\d+)\s*([a-z]+)$", raw)
    if not match:
        return None
    val = int(match.group(1))
    unit = match.group(2)

    if unit in ("s", "sec", "secs", "second", "seconds"):
        return float(val)
    elif unit in ("m", "min", "mins", "minute", "minutes"):
        return float(val * 60)
    elif unit in ("h", "hr", "hrs", "hour", "hours"):
        return float(val * 3600)
    elif unit in ("d", "day", "days"):
        return float(val * 86400)
    elif unit in ("w", "wk", "wks", "week", "weeks"):
        return float(val * 604800)
    return None


def resolve_target_channel(
    guild: discord.Guild,
    channel_query: Optional[Any],
    default_channel: Optional[discord.TextChannel] = None
) -> Tuple[Optional[discord.TextChannel], Optional[str]]:
    """
    Resolves a channel from a mention (<#123>), an ID ('123'), a prefixed name ('#giveaways'),
    or plain name ('giveaways') against the current guild.
    Returns (resolved_channel, error_message).
    """
    if not guild:
        return default_channel, None
    if not channel_query:
        return default_channel, None

    query_str = str(channel_query).strip()

    # 1. Mention: <#123456789>
    m_mention = re.search(r"<#(\d+)>", query_str)
    if m_mention:
        cid = int(m_mention.group(1))
        ch = guild.get_channel(cid)
        if ch and isinstance(ch, discord.TextChannel):
            return ch, None
        return None, f"Channel <#{cid}> not found in this server."

    # 2. Raw digits ID: 123456789
    clean_digits = query_str.lstrip("#")
    if clean_digits.isdigit():
        cid = int(clean_digits)
        ch = guild.get_channel(cid)
        if ch and isinstance(ch, discord.TextChannel):
            return ch, None

    # 3. Channel Name (exact match case-insensitive, with or without leading #)
    name_clean = query_str.lstrip("#").strip().lower()
    text_channels = getattr(guild, "text_channels", [])
    for ch in text_channels:
        if ch.name.lower() == name_clean:
            return ch, None

    # 4. Partial substring match among text channels if unique
    matches = [ch for ch in text_channels if name_clean in ch.name.lower()]
    if len(matches) == 1:
        return matches[0], None

    return None, f"Could not find a text channel matching '{query_str}' in this server."


@dataclass
class GiveawayDraft:
    user_id: int
    guild_id: int
    conversation_channel_id: int
    prize: str
    target_channel_id: Optional[int] = None
    winners: int = 1
    duration: Optional[str] = None
    claim_duration_seconds: int = 900
    created_at: float = field(default_factory=time.time)
    timeout_seconds: float = 300.0

    def is_expired(self) -> bool:
        return (time.time() - self.created_at) > self.timeout_seconds


class GiveawayDraftManager:
    """Tracks active conversational giveaway drafts per guild, channel, and user."""
    def __init__(self, default_ttl: float = 300.0):
        self.default_ttl = default_ttl
        self._drafts: Dict[Tuple[int, int, int], GiveawayDraft] = {}

    def _resolve_key(self, arg1: int, arg2: int, arg3: Optional[int] = None) -> Tuple[int, int, int]:
        if arg3 is not None:
            return (int(arg1), int(arg2), int(arg3))
        # Legacy fallback: (user_id, guild_id)
        for (g_id, c_id, u_id) in list(self._drafts.keys()):
            if g_id == int(arg2) and u_id == int(arg1):
                return (g_id, c_id, u_id)
        return (int(arg2), 0, int(arg1))

    def create_draft(
        self,
        *args,
        user_id: Optional[int] = None,
        guild_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        conversation_channel_id: Optional[int] = None,
        prize: str = "Prize",
        target_channel_id: Optional[int] = None,
        winners: int = 1,
        claim_duration_seconds: int = 900,
        timeout_seconds: Optional[float] = None,
        **kwargs
    ) -> GiveawayDraft:
        if len(args) == 3:
            g_id, c_id, u_id = int(args[0]), int(args[1]), int(args[2])
        elif len(args) == 2:
            u_id, g_id = int(args[0]), int(args[1])
            c_id = int(conversation_channel_id or channel_id or 0)
        else:
            g_id = int(guild_id or kwargs.get("guild_id", 0))
            c_id = int(channel_id or conversation_channel_id or kwargs.get("conversation_channel_id", 0))
            u_id = int(user_id or kwargs.get("user_id", 0))

        ttl = timeout_seconds if timeout_seconds is not None else self.default_ttl
        draft = GiveawayDraft(
            user_id=u_id,
            guild_id=g_id,
            conversation_channel_id=c_id,
            prize=prize,
            target_channel_id=target_channel_id,
            winners=winners,
            claim_duration_seconds=claim_duration_seconds,
            timeout_seconds=ttl
        )
        self._drafts[(g_id, c_id, u_id)] = draft
        return draft

    def get_draft(
        self,
        *args,
        guild_id: Optional[int] = None,
        channel_id: Optional[int] = None,
        user_id: Optional[int] = None,
        **kwargs
    ) -> Optional[GiveawayDraft]:
        if len(args) == 3:
            key = (int(args[0]), int(args[1]), int(args[2]))
        elif len(args) == 2:
            key = self._resolve_key(args[0], args[1])
        else:
            g_id = int(guild_id or kwargs.get("guild_id", 0))
            c_id = int(channel_id or kwargs.get("channel_id", 0))
            u_id = int(user_id or kwargs.get("user_id", 0))
            key = (g_id, c_id, u_id)

        draft = self._drafts.get(key)
        if not draft:
            return None
        if draft.is_expired():
            self._drafts.pop(key, None)
            return None
        return draft

    def remove_draft(self, *args, **kwargs) -> Optional[GiveawayDraft]:
        if len(args) == 3:
            key = (int(args[0]), int(args[1]), int(args[2]))
        elif len(args) == 2:
            key = self._resolve_key(args[0], args[1])
        else:
            g_id = int(kwargs.get("guild_id", 0))
            c_id = int(kwargs.get("channel_id", 0))
            u_id = int(kwargs.get("user_id", 0))
            key = (g_id, c_id, u_id)
        return self._drafts.pop(key, None)

    def cancel_draft(self, *args, **kwargs) -> bool:
        return self.remove_draft(*args, **kwargs) is not None


giveaway_drafts = GiveawayDraftManager()


# -----------------------------------------------------------------------------
# Append-Only Hash-Chained Giveaway Audit Ledger
# -----------------------------------------------------------------------------
class GiveawayIntegrityResult(tuple):
    """Dual tuple-dict result for audit ledger integrity checks."""
    def __new__(cls, is_valid: bool, verified_count: int, error: Optional[str] = None):
        return super().__new__(cls, (is_valid, verified_count, error))

    @property
    def valid(self) -> bool:
        return self[0]

    @property
    def events_verified(self) -> int:
        return self[1]

    @property
    def error(self) -> Optional[str]:
        return self[2]

    def __getitem__(self, item):
        if isinstance(item, str):
            if item == "valid":
                return self[0]
            elif item in ("events_verified", "verified_count"):
                return self[1]
            elif item == "error":
                return self[2]
            raise KeyError(item)
        return super().__getitem__(item)

    def get(self, key, default=None):
        try:
            return self[key]
        except KeyError:
            return default


class GiveawayAuditLedger:
    """Maintains an append-only, SHA-256 hash-chained audit trail for all giveaway operations."""

    def __init__(self, db: Optional[FeatureDatabase] = None, ledger_path: Optional[str] = None):
        self.db = db
        self.audit_path = ledger_path
        if not self.audit_path:
            db_inst = self.db or get_feature_db()
            self.audit_path = os.path.join(getattr(db_inst, "persist_dir", "isa_memory"), "giveaway_audit.json")
        self.events: List[Dict[str, Any]] = []
        self._load()

    def _load(self):
        if self.audit_path and os.path.exists(self.audit_path):
            try:
                with open(self.audit_path, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content.startswith("["):
                        self.events = json.loads(content)
                    else:
                        # JSONL format support
                        self.events = [json.loads(line) for line in content.splitlines() if line.strip()]
            except Exception:
                self.events = []
        else:
            self.events = []

    def _persist(self):
        if not self.audit_path:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.audit_path)), exist_ok=True)
            with open(self.audit_path, "w", encoding="utf-8") as f:
                json.dump(self.events, f, indent=2)
        except Exception:
            pass

    def record_event(self, giveaway_id: str, event_type: str, actor_id: Any = "SYSTEM", details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Appends a cryptographically hash-chained event to the ledger."""
        if details is None and isinstance(actor_id, dict):
            details = actor_id
            actor_id = "SYSTEM"
        elif details is None:
            details = {}

        prev_hash = self.events[-1]["hash"] if self.events else "GENESIS"
        now_iso = datetime.now(timezone.utc).isoformat()
        event_id = f"evt_{giveaway_id}_{len(self.events) + 1}_{int(time.time())}"

        event_payload = {
            "event_id": event_id,
            "giveaway_id": str(giveaway_id),
            "event_type": event_type,
            "timestamp": now_iso,
            "actor_id": str(actor_id),
            "details": details,
            "prev_hash": prev_hash,
            "previous_hash": prev_hash
        }

        # SHA-256 integrity hash
        hash_input = f"{prev_hash}|{event_id}|{giveaway_id}|{event_type}|{now_iso}|{actor_id}|{json.dumps(details, sort_keys=True)}"
        calc_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
        event_payload["hash"] = calc_hash
        event_payload["record_hash"] = calc_hash

        self.events.append(event_payload)
        self._persist()
        return event_payload

    def verify_integrity(self, giveaway_id: Optional[str] = None) -> GiveawayIntegrityResult:
        """
        Verifies the SHA-256 hash chain.
        Returns a GiveawayIntegrityResult supporting both tuple and dict access.
        """
        self._load()
        if not self.events:
            return GiveawayIntegrityResult(True, 0, None)

        events_to_check = self.events
        if giveaway_id:
            events_to_check = [e for e in self.events if e.get("giveaway_id") == str(giveaway_id)]

        for i, ev in enumerate(self.events):
            ev_prev = ev.get("prev_hash") or ev.get("previous_hash")
            expected_prev = self.events[i - 1]["hash"] if i > 0 else (ev_prev if ev_prev in ("GENESIS", "GENESIS_GIVEAWAY_ANCHOR") else "GENESIS")
            if ev_prev != expected_prev:
                return GiveawayIntegrityResult(False, i, f"Hash broken at event #{i + 1} ({ev.get('event_id')}): prev_hash mismatch.")

            # Recalculate hash
            hash_input = f"{expected_prev}|{ev['event_id']}|{ev['giveaway_id']}|{ev['event_type']}|{ev['timestamp']}|{ev['actor_id']}|{json.dumps(ev['details'], sort_keys=True)}"
            calc_hash = hashlib.sha256(hash_input.encode("utf-8")).hexdigest()
            ev_hash = ev.get("hash") or ev.get("record_hash")
            if calc_hash != ev_hash:
                return GiveawayIntegrityResult(False, i, f"Tampering detected at event #{i + 1} ({ev.get('event_id')}): calculated hash does not match stored hash.")

        return GiveawayIntegrityResult(True, len(events_to_check), None)


audit_ledger = GiveawayAuditLedger()


# -----------------------------------------------------------------------------
# Interactive Views: Entry & Claim
# -----------------------------------------------------------------------------
class GiveawayEntryView(discord.ui.View):
    """Interactive button allowing members to enter or leave the giveaway."""
    def __init__(self, message_id: str = "pending"):
        super().__init__(timeout=None)
        self.message_id = str(message_id)

    @discord.ui.button(label="Enter Giveaway", style=discord.ButtonStyle.success, emoji="🎉", custom_id="kazumi:giveaway:enter")
    async def enter_giveaway(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 1. Reject bots
        if getattr(interaction.user, "bot", False):
            await interaction.response.send_message("❌ Bots cannot enter giveaways.", ephemeral=True)
            return

        db = get_feature_db()
        mid = str(interaction.message.id) if interaction.message else self.message_id
        giveaway = db.get_giveaway(mid)
        if not giveaway or giveaway.get("ended", False) or giveaway.get("status") in (
            GiveawayState.COMPLETED.value, GiveawayState.DRAWING.value, GiveawayState.CLAIM_PENDING.value,
            GiveawayState.CANCELLED.value, GiveawayState.NO_ELIGIBLE_ENTRANTS.value
        ):
            await interaction.response.send_message("❌ This giveaway is not accepting entries.", ephemeral=True)
            return

        if giveaway.get("paused", False):
            await interaction.response.send_message("⏸️ This giveaway is currently paused by staff.", ephemeral=True)
            return

        # Check required role
        req_role_id = giveaway.get("required_role_id")
        if req_role_id:
            role = interaction.guild.get_role(int(req_role_id))
            if role and role not in interaction.user.roles:
                await interaction.response.send_message(f"❌ You require the {role.mention} role to enter this giveaway.", ephemeral=True)
                return

        # Check minimum account age
        min_acc_days = giveaway.get("min_account_days", 0)
        if min_acc_days > 0:
            now_dt = datetime.now(timezone.utc)
            acc_age_days = (now_dt - interaction.user.created_at).total_seconds() / 86400
            if acc_age_days < min_acc_days:
                await interaction.response.send_message(f"❌ Your Discord account must be at least **{min_acc_days} days** old to enter (yours is {int(acc_age_days)} days).", ephemeral=True)
                return

        # Check minimum server membership age
        min_srv_days = giveaway.get("min_server_days", 0)
        if min_srv_days > 0 and hasattr(interaction.user, "joined_at") and interaction.user.joined_at:
            now_dt = datetime.now(timezone.utc)
            joined_days = (now_dt - interaction.user.joined_at).total_seconds() / 86400
            if joined_days < min_srv_days:
                await interaction.response.send_message(f"❌ You must be a member of this server for at least **{min_srv_days} days** to enter.", ephemeral=True)
                return

        entries = list(giveaway.get("entries", []))
        uid = str(interaction.user.id)
        if uid in entries:
            entries.remove(uid)
            giveaway["entries"] = entries
            db.save_giveaway(mid, giveaway)
            audit_ledger.record_event(mid, "LEAVE", uid, {"remaining_entries": len(entries)})
            await interaction.response.send_message("👋 You left the giveaway. Click again anytime to re-enter!", ephemeral=True)
        else:
            entries.append(uid)
            giveaway["entries"] = entries
            db.save_giveaway(mid, giveaway)
            audit_ledger.record_event(mid, "ENTRY", uid, {"total_entries": len(entries)})
            await interaction.response.send_message(f"🎉 You have entered the giveaway for **{giveaway['prize']}**! Total entries: **{len(entries)}**", ephemeral=True)


_giveaway_async_locks: Dict[str, asyncio.Lock] = {}

def get_giveaway_lock(message_id: str) -> asyncio.Lock:
    mid = str(message_id)
    if mid not in _giveaway_async_locks:
        _giveaway_async_locks[mid] = asyncio.Lock()
    return _giveaway_async_locks[mid]


class GiveawayClaimView(discord.ui.View):
    """Interactive button allowing the selected winner to securely claim their prize."""
    def __init__(self, message_id: str = "pending"):
        super().__init__(timeout=None)
        self.message_id = str(message_id)

    @discord.ui.button(label="Claim Prize 🎁", style=discord.ButtonStyle.primary, emoji="✨", custom_id="kazumi:giveaway:claim")
    async def claim_prize(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        mid = str(interaction.message.id) if interaction.message else self.message_id
        lock = get_giveaway_lock(mid)
        async with lock:
            db = get_feature_db()
            giveaway = db.get_giveaway(mid)
            if not giveaway:
                await interaction.response.send_message("❌ Giveaway record not found.", ephemeral=True)
                return

            # Check if giveaway is in terminal state
            if giveaway.get("status") in (
                GiveawayState.COMPLETED.value,
                GiveawayState.CANCELLED.value,
                GiveawayState.NO_ELIGIBLE_ENTRANTS.value
            ):
                claimed_users = set(giveaway.get("claimed_winners", []))
                if uid in claimed_users:
                    await interaction.response.send_message("✅ You have already claimed this prize! The host has your claim on file.", ephemeral=True)
                else:
                    await interaction.response.send_message("❌ This giveaway is already concluded.", ephemeral=True)
                return

            current_winners = list(giveaway.get("current_pending_winners", giveaway.get("winners", [])))

            if uid not in current_winners:
                claimed_users = set(giveaway.get("claimed_winners", []))
                if uid in claimed_users:
                    await interaction.response.send_message("✅ You have already claimed this prize! The host has your claim on file.", ephemeral=True)
                    return
                await interaction.response.send_message("❌ Only the currently drawn winner can claim this prize!", ephemeral=True)
                return

            # Check claim deadline
            deadline = giveaway.get("claim_deadline")
            now = time.time()
            if giveaway.get("claim_deadline_enabled", True) and deadline and now > deadline:
                await interaction.response.send_message("⏱️ The claim deadline has expired. This prize is being rerolled.", ephemeral=True)
                return

            # Atomically mark claimed under lock
            giveaway.setdefault("claimed_winners", []).append(uid)
            if uid in current_winners:
                current_winners.remove(uid)
            giveaway["current_pending_winners"] = current_winners
            if not current_winners:
                giveaway["status"] = GiveawayState.COMPLETED.value
            else:
                giveaway["status"] = GiveawayState.CLAIM_PENDING.value
            db.save_giveaway(mid, giveaway)

            audit_ledger.record_event(mid, "CLAIMED", uid, {"prize": giveaway.get("prize", "")})

            button.disabled = True
            button.label = "Claimed! ✅"
            try:
                await interaction.response.edit_message(view=self)
            except Exception:
                pass
            await interaction.followup.send(f"🎉 Congratulations {interaction.user.mention}! Your claim for **{giveaway.get('prize')}** is confirmed! The host has been notified. 🌸")

            # Notify host via DM
            try:
                host_id = int(giveaway.get("host_id", 0))
                if interaction.guild and host_id:
                    host = interaction.guild.get_member(host_id) or await interaction.guild.fetch_member(host_id)
                    if host:
                        await host.send(f"🎁 **Giveaway Claimed:** {interaction.user.mention} ({interaction.user}) has confirmed their claim for **{giveaway.get('prize')}** in **{interaction.guild.name}**!")
            except Exception as e:
                logger.debug(f"Could not send DM to host: {e}")


async def create_giveaway_execution(
    bot: commands.Bot,
    guild: discord.Guild,
    host: discord.Member,
    prize: str,
    duration_str: str,
    target_channel: discord.TextChannel,
    winners_count: int = 1,
    announcement_channel: Optional[discord.TextChannel] = None,
    claim_duration_seconds: int = 900,
    claim_deadline_enabled: bool = True,
    required_role: Optional[discord.Role] = None
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Creates and activates an authoritative giveaway.
    Posts main embed with persistent entry button to target_channel.
    If announcement_channel is provided or configured, publishes announcement embed with jump link.
    Persists giveaway record to database and audit ledger.
    """
    db = get_feature_db()

    # Verify bot permissions in target channel
    if hasattr(guild, "me") and guild.me:
        perms = target_channel.permissions_for(guild.me)
        if not perms.send_messages or not perms.embed_links:
            return False, f"❌ I lack permissions to send messages or embed links in {target_channel.mention}!", None

    secs = parse_duration(duration_str)
    if not secs or secs < 10:
        return False, "❌ Duration must be at least 10 seconds (e.g. `10m`, `2h`, `1d`).", None

    end_timestamp = time.time() + secs
    num_w = max(1, min(20, winners_count))

    # Resolve announcement channel if not explicitly passed
    if not announcement_channel:
        try:
            guild_settings = db.get_guild_settings(str(guild.id))
            ann_cid = guild_settings.get("giveaway_announcement_channel_id") or os.environ.get("GIVEAWAY_ANNOUNCEMENT_CHANNEL_ID") or os.environ.get("DISCORD_GIVEAWAY_ANNOUNCEMENT_CHANNEL_ID")
            if ann_cid:
                ch = guild.get_channel(int(ann_cid))
                if isinstance(ch, discord.TextChannel):
                    announcement_channel = ch
        except Exception:
            pass

    claim_mins = claim_duration_seconds // 60
    claim_mode_text = f"\n**Claim Window:** {claim_mins} minutes per winner" if claim_deadline_enabled else "\n**Mode:** Permanent Claim (No timeout)"
    req_role_text = f"\n**Required Role:** {required_role.mention}" if required_role else ""

    embed = discord.Embed(
        title=f"🎉 GIVEAWAY: {prize}!",
        description=(
            f"Click **Enter Giveaway** below to participate!\n\n"
            f"**Prize:** **{prize}**\n"
            f"**Winners:** `{num_w}`\n"
            f"**Ends:** <t:{int(end_timestamp)}:R> (<t:{int(end_timestamp)}:f>)\n"
            f"**Hosted by:** {host.mention}"
            f"{claim_mode_text}{req_role_text}"
        ),
        color=0xf43f5e
    )
    embed.set_footer(text="Kazumi Giveaway System 🌸 • Cryptographically Fair")

    entry_view = GiveawayEntryView("pending")
    main_msg = await target_channel.send(embed=embed, view=entry_view)

    # Publish in announcement channel if configured and distinct
    ann_msg_id = None
    ann_cid = None
    if announcement_channel and announcement_channel.id != target_channel.id:
        ann_perms = announcement_channel.permissions_for(guild.me) if hasattr(guild, "me") and guild.me else None
        if not ann_perms or (ann_perms.send_messages and ann_perms.embed_links):
            try:
                ann_embed = discord.Embed(
                    title=f"🎉 NEW GIVEAWAY ANNOUNCEMENT: {prize}!",
                    description=(
                        f"A new giveaway has started in {target_channel.mention}!\n\n"
                        f"**Prize:** **{prize}**\n"
                        f"**Winners:** `{num_w}`\n"
                        f"**Ends:** <t:{int(end_timestamp)}:R> (<t:{int(end_timestamp)}:f>)\n"
                        f"**Hosted by:** {host.mention}\n\n"
                        f"👉 **[Click here to enter the giveaway!]({main_msg.jump_url})**"
                    ),
                    color=0xec4899
                )
                ann_embed.set_footer(text="Kazumi Giveaway System 🌸 • Announcements")
                ann_msg = await announcement_channel.send(embed=ann_embed)
                ann_msg_id = str(ann_msg.id)
                ann_cid = str(announcement_channel.id)
            except Exception as e:
                logger.warning(f"Failed to post to giveaway announcement channel: {e}")

    giveaway_data = {
        "id": str(main_msg.id),
        "message_id": str(main_msg.id),
        "channel_id": str(target_channel.id),
        "target_channel_id": str(target_channel.id),
        "announcement_channel_id": ann_cid,
        "announcement_message_id": ann_msg_id,
        "guild_id": str(guild.id),
        "host_id": str(host.id),
        "prize": prize,
        "winners_count": num_w,
        "winners": [],
        "current_pending_winners": [],
        "claimed_winners": [],
        "disqualified_winners": [],
        "entries": [],
        "draw_history": [],
        "creation_time": time.time(),
        "end_time": end_timestamp,
        "claim_deadline_enabled": claim_deadline_enabled,
        "claim_duration_seconds": claim_duration_seconds,
        "claim_deadline": None,
        "required_role_id": str(required_role.id) if required_role else None,
        "ended": False,
        "paused": False,
        "status": GiveawayState.ACTIVE.value
    }
    db.save_giveaway(str(main_msg.id), giveaway_data)
    audit_ledger.record_event(str(main_msg.id), "CREATED", str(host.id), {
        "prize": prize,
        "target_channel": str(target_channel.id),
        "winners": num_w,
        "end_time": end_timestamp,
        "claim_duration_seconds": claim_duration_seconds
    })

    ann_note = f" and announced in {announcement_channel.mention}" if ann_msg_id else ""
    return True, f"🎉 Giveaway for **{prize}** created successfully in {target_channel.mention}{ann_note}!", giveaway_data


# -----------------------------------------------------------------------------
# Core Giveaway Manager
# -----------------------------------------------------------------------------
class GiveawayManager:
    """Manages active giveaways, cryptographic random selection, claim windows, and rerolls."""

    def __init__(self, bot: Any = None, db: Any = None, storage_file: Optional[str] = None):
        self.bot = bot
        self.db = db or get_feature_db()
        self.storage_file = storage_file
        self.giveaways: Dict[str, Any] = {}
        if self.storage_file and os.path.exists(self.storage_file):
            try:
                with open(self.storage_file, "r", encoding="utf-8") as f:
                    self.giveaways = json.load(f)
            except Exception:
                self.giveaways = {}

    def _persist(self):
        if self.storage_file:
            try:
                os.makedirs(os.path.dirname(os.path.abspath(self.storage_file)), exist_ok=True)
                with open(self.storage_file, "w", encoding="utf-8") as f:
                    json.dump(self.giveaways, f, indent=2)
            except Exception:
                pass

    def pick_winners(
        self,
        giveaway_id: str,
        eligible_entrants: List[Any],
        winner_count: int = 1,
        claim_mode: str = "MODE_A",
        claim_window_seconds: Optional[float] = 86400
    ) -> List[Dict[str, Any]]:
        unique_entrants = list(dict.fromkeys(eligible_entrants))
        picks = self.draw_cryptographic_winner(unique_entrants, winner_count)
        now = time.time()
        deadline = (now + claim_window_seconds) if (claim_mode == "MODE_A" and claim_window_seconds) else None

        winners_list = []
        for p in picks:
            winners_list.append({
                "user_id": p,
                "status": "AWAITING_CLAIM",
                "attempt_number": 1,
                "claim_deadline": deadline
            })

        self.giveaways[giveaway_id] = {
            "giveaway_id": giveaway_id,
            "entrants": unique_entrants,
            "winners": winners_list,
            "winner_history": [],
            "claim_mode": claim_mode,
            "claim_window_seconds": claim_window_seconds,
            "status": "AWAITING_CLAIM"
        }
        self._persist()
        return winners_list

    def reroll_expired_winner(
        self,
        giveaway_id: str,
        prize_index: int = 0,
        eligible_entrants: Optional[List[Any]] = None
    ) -> Optional[Dict[str, Any]]:
        gw = self.giveaways.get(giveaway_id)
        if not gw or not gw.get("winners"):
            return None

        if prize_index >= len(gw["winners"]):
            return None

        old_winner = gw["winners"][prize_index]
        old_winner["status"] = "EXPIRED"
        gw.setdefault("winner_history", []).append(dict(old_winner))

        entrants = eligible_entrants or gw.get("entrants", [])
        past_winners = {w["user_id"] for w in gw["winner_history"]} | {w["user_id"] for w in gw["winners"]}
        remaining = [e for e in entrants if e not in past_winners]

        if not remaining:
            return None

        new_picks = self.draw_cryptographic_winner(remaining, 1)
        if not new_picks:
            return None
        new_pick = new_picks[0]

        claim_dur = gw.get("claim_window_seconds", 86400) or 86400
        new_deadline = time.time() + claim_dur if gw.get("claim_mode") == "MODE_A" else None

        replacement = {
            "user_id": new_pick,
            "status": "AWAITING_CLAIM",
            "attempt_number": old_winner.get("attempt_number", 1) + 1,
            "claim_deadline": new_deadline
        }
        gw["winners"][prize_index] = replacement
        self._persist()
        return replacement

    async def end_giveaway(self, message_id: str) -> List[str]:
        giveaway = self.db.get_giveaway(message_id)
        if not giveaway:
            return []
        giveaway["ended"] = True
        entries = list(dict.fromkeys(giveaway.get("entries", [])))
        num_winners = max(1, giveaway.get("winners_count", 1))
        winners = self.draw_cryptographic_winner(entries, num_winners)
        giveaway["winners"] = winners
        giveaway["current_pending_winners"] = list(winners)
        if hasattr(self.db, "set_giveaway"):
            self.db.set_giveaway(message_id, giveaway)
        else:
            self.db.save_giveaway(message_id, giveaway)

        if self.bot and hasattr(self.bot, "get_channel"):
            try:
                ch = self.bot.get_channel(int(giveaway.get("channel_id", 0)))
                if ch:
                    msg = await ch.fetch_message(int(message_id))
                    if msg:
                        await msg.edit(embed=discord.Embed(title=f"Giveaway Ended: {giveaway.get('prize')}"))
            except Exception:
                pass

        audit_ledger.record_event(message_id, "DRAWN", "SYSTEM", {"winners": winners})
        return winners

    async def reroll_giveaway(self, message_id: str) -> List[str]:
        giveaway = self.db.get_giveaway(message_id)
        if not giveaway:
            return []
        entries = list(dict.fromkeys(giveaway.get("entries", [])))
        past_winners = set(giveaway.get("winners", []))
        eligible = [e for e in entries if e not in past_winners]
        if not eligible:
            eligible = entries
        num_winners = max(1, giveaway.get("winners_count", 1))
        new_picks = self.draw_cryptographic_winner(eligible, num_winners)
        giveaway["winners"] = new_picks
        giveaway["current_pending_winners"] = list(new_picks)
        if hasattr(self.db, "set_giveaway"):
            self.db.set_giveaway(message_id, giveaway)
        else:
            self.db.save_giveaway(message_id, giveaway)
        audit_ledger.record_event(message_id, "REROLLED", "SYSTEM", {"replacement_winners": new_picks})
        return new_picks

    @staticmethod
    def enter_giveaway(guild_id: str, message_id: str, user_id: Any, db: Any = None, member: Any = None) -> Tuple[bool, str]:
        if db is None:
            db = get_feature_db()
        if member and getattr(member, "bot", False) is True:
            return False, "Bots cannot enter giveaways."
        giveaway = db.get_giveaway(message_id)
        if not giveaway:
            return False, "Giveaway not found."
        if giveaway.get("ended", False):
            return False, "This giveaway has already ended."
        if giveaway.get("paused", False):
            return False, "This giveaway is currently paused."

        req_role_id = giveaway.get("required_role_id")
        if req_role_id and member:
            has_role = any(str(r.id) == str(req_role_id) for r in getattr(member, "roles", []))
            if not has_role:
                return False, "You lack the required role to enter."

        entries = list(giveaway.get("entries", []))
        uid = str(user_id)
        if uid in entries:
            return False, "You have already entered this giveaway."

        entries.append(uid)
        giveaway["entries"] = entries
        db.save_giveaway(message_id, giveaway)
        audit_ledger.record_event(message_id, "ENTRY", uid, {"total_entries": len(entries)})
        return True, f"Successfully entered the giveaway for {giveaway.get('prize')}!"

    @staticmethod
    def draw_cryptographic_winner(eligible_entries: List[str], count: int = 1) -> List[str]:
        """Draws winners using cryptographically secure secrets.SystemRandom."""
        if not eligible_entries:
            return []
        unique_pool = list(dict.fromkeys(eligible_entries))  # Deduplicate preserving order
        num_picks = min(count, len(unique_pool))
        return sys_random.sample(unique_pool, num_picks)

    @classmethod
    async def finish_giveaway(cls, bot: commands.Bot, message_id: str):
        """Concludes giveaway, selects winner cryptographically, and begins claim window."""
        mid_str = str(message_id)
        lock = get_giveaway_lock(mid_str)
        async with lock:
            db = get_feature_db()
            giveaway = db.get_giveaway(mid_str)
            if not giveaway or giveaway.get("ended", False):
                return

            giveaway["ended"] = True
            giveaway["status"] = GiveawayState.DRAWING.value
            db.save_giveaway(mid_str, giveaway)

            guild = bot.get_guild(int(giveaway["guild_id"])) if bot else None
            channel = guild.get_channel(int(giveaway["channel_id"])) if guild else None
            message = None
            if channel:
                try:
                    message = await channel.fetch_message(int(message_id))
                except Exception as e:
                    logger.warning(f"Failed to fetch giveaway message {message_id}: {e}")

            # Check entries and filter out bots
            raw_entries = list(dict.fromkeys(giveaway.get("entries", [])))
            entries = []
            if guild:
                for uid in raw_entries:
                    try:
                        m = guild.get_member(int(uid))
                        if m and getattr(m, "bot", False):
                            continue
                    except Exception:
                        pass
                    entries.append(uid)
            else:
                entries = raw_entries

            num_winners = max(1, giveaway.get("winners_count", 1))
            prize = giveaway.get("prize", "Surprise Gift")

            if not entries:
                giveaway["status"] = GiveawayState.NO_ELIGIBLE_ENTRANTS.value
                db.save_giveaway(message_id, giveaway)
                embed = discord.Embed(
                    title=f"🎉 Giveaway Concluded: {prize}",
                    description="Unfortunately, no eligible members entered the giveaway.",
                    color=0x94a3b8
                )
                embed.set_footer(text="Kazumi Giveaway System 🌸 • Cryptographically Fair")
                if message:
                    try:
                        await message.edit(embed=embed, view=None)
                    except Exception:
                        pass
                if channel:
                    try:
                        await channel.send(f"🎉 The giveaway for **{prize}** ended with zero entries.")
                    except Exception:
                        pass
                audit_ledger.record_event(message_id, "CLOSED", "SYSTEM", {"reason": "No entries"})
                return

            # Select initial winners cryptographically using SystemRandom
            winners = cls.draw_cryptographic_winner(entries, num_winners)
            giveaway["winners"] = winners
            giveaway["current_pending_winners"] = list(winners)
            giveaway["disqualified_winners"] = []
            giveaway["claimed_winners"] = []

            # Claim deadline calculation (default 15 minutes / 900s if not specified)
            deadline_enabled = giveaway.get("claim_deadline_enabled", True)
            claim_dur = giveaway.get("claim_duration_seconds", 900)
            claim_deadline = time.time() + claim_dur if deadline_enabled else None
            giveaway["claim_deadline"] = claim_deadline
            giveaway["status"] = GiveawayState.CLAIM_PENDING.value
            db.save_giveaway(message_id, giveaway)

            audit_ledger.record_event(message_id, "DRAWN", "SYSTEM", {
                "winners": winners,
                "claim_deadline_enabled": deadline_enabled,
                "claim_deadline": claim_deadline
            })

            winner_mentions = [f"<@{w}>" for w in winners]
            claim_desc = f"\n\n⏳ **Claim Deadline:** <t:{int(claim_deadline)}:R> (<t:{int(claim_deadline)}:f>)" if claim_deadline else "\n\n*(No automatic claim expiry)*"

            embed = discord.Embed(
                title=f"🎉 Giveaway Winner Drawn: {prize}!",
                description=(
                    f"**Congratulations:** {', '.join(winner_mentions)}!\n"
                    f"**Total Valid Entries:** `{len(entries)}`"
                    f"{claim_desc}\n\n"
                    f"Please click the **Claim Prize** button below to confirm your prize! 🌸"
                ),
                color=0xf59e0b
            )
            embed.set_footer(text="Kazumi Giveaway System 🌸 • Cryptographically Fair")

            claim_view = GiveawayClaimView(message_id)
            if message:
                try:
                    await message.edit(embed=embed, view=claim_view)
                except Exception:
                    pass
            if channel:
                try:
                    await channel.send(
                        f"🎉 Congratulations {', '.join(winner_mentions)}! You have won **{prize}**! Please claim before your window expires: 🎁",
                        view=claim_view
                    )
                except Exception as e:
                    logger.warning(f"Failed to post giveaway winner announcement: {e}")

            # Notify winners via DM
            jump_url = message.jump_url if message else ""
            if guild:
                for w in winners:
                    try:
                        w_member = guild.get_member(int(w)) or await guild.fetch_member(int(w))
                        if w_member and not getattr(w_member, "bot", False):
                            dm_text = (
                                f"🎉 **Congratulations! You won the giveaway for {prize} in {guild.name}!**\n"
                                f"👉 Claim your prize here: {jump_url}\n"
                            )
                            if claim_deadline:
                                dm_text += f"⏳ **Claim Deadline:** <t:{int(claim_deadline)}:R>\n"
                            await w_member.send(dm_text)
                    except Exception as dm_err:
                        logger.debug(f"Could not send DM to winner {w}: {dm_err}")

                # Notify host via DM
                host_id = int(giveaway.get("host_id", 0))
                if host_id:
                    try:
                        h_member = guild.get_member(host_id) or await guild.fetch_member(host_id)
                        if h_member:
                            await h_member.send(
                                f"🎁 **Giveaway Drawn:** Winner(s) for your **{prize}** giveaway in **{guild.name}** have been drawn: {', '.join(winner_mentions)}!\n"
                                f"Link: {jump_url}"
                            )
                    except Exception as h_err:
                        logger.debug(f"Could not send DM to host {host_id}: {h_err}")

            # Update announcement channel if present
            ann_cid = giveaway.get("announcement_channel_id")
            if guild and ann_cid:
                try:
                    ann_ch = guild.get_channel(int(ann_cid))
                    if ann_ch and isinstance(ann_ch, discord.TextChannel):
                        ann_embed = discord.Embed(
                            title=f"🎉 GIVEAWAY WINNER: {prize}!",
                            description=(
                                f"Winners have been drawn for **{prize}** in {channel.mention if channel else ''}!\n\n"
                                f"**Winner(s):** {', '.join(winner_mentions)}\n"
                                f"👉 **[Click here to view the giveaway and claim]({jump_url})**"
                            ),
                            color=0xf59e0b
                        )
                        ann_embed.set_footer(text="Kazumi Giveaway System 🌸 • Winner Announcement")
                        await ann_ch.send(embed=ann_embed)
                except Exception as ann_err:
                    logger.debug(f"Could not update announcement channel: {ann_err}")

    @classmethod
    async def process_expired_claim_reroll(cls, bot: commands.Bot, message_id: str):
        """
        Handles automatic winner replacement when claim deadline expires in Mode A.
        Marks expired winner, selects new winner from remaining pool, and grants fresh claim window.
        """
        mid_str = str(message_id)
        lock = get_giveaway_lock(mid_str)
        async with lock:
            db = get_feature_db()
            giveaway = db.get_giveaway(mid_str)
            if not giveaway or not giveaway.get("claim_deadline_enabled", True):
                return

            # Abort if giveaway is terminal
            if giveaway.get("status") in (
                GiveawayState.COMPLETED.value,
                GiveawayState.CANCELLED.value,
                GiveawayState.NO_ELIGIBLE_ENTRANTS.value
            ):
                return

            now = time.time()
            deadline = giveaway.get("claim_deadline")
            if not deadline or now <= deadline:
                return

            prior_status = giveaway.get("status")
            # Mark state as actively drawing to prevent concurrent tasks
            giveaway["status"] = GiveawayState.DRAWING.value
            db.save_giveaway(mid_str, giveaway)

            pending = list(giveaway.get("current_pending_winners", []))
            claimed = set(giveaway.get("claimed_winners", []))
            unclaimed = [u for u in pending if u not in claimed]

            if not unclaimed:
                giveaway["status"] = GiveawayState.COMPLETED.value
                db.save_giveaway(mid_str, giveaway)
                return

            # Mark unclaimed as disqualified / expired
            disqualified = giveaway.setdefault("disqualified_winners", [])
            disqualified.extend(unclaimed)
            for u in unclaimed:
                audit_ledger.record_event(mid_str, "EXPIRED", u, {"reason": "Claim window expired"})
                giveaway.setdefault("draw_history", []).append({
                    "user_id": u,
                    "status": "EXPIRED",
                    "timestamp": now
                })

            # Pick replacement winners from remaining pool
            all_entries = list(dict.fromkeys(giveaway.get("entries", [])))
            all_past_winners = set(giveaway.get("winners", []) + disqualified + list(claimed))
            remaining_pool = [uid for uid in all_entries if uid not in all_past_winners]

            guild = bot.get_guild(int(giveaway["guild_id"])) if bot else None
            channel = guild.get_channel(int(giveaway["channel_id"])) if guild else None
            message = None
            if channel:
                try:
                    message = await channel.fetch_message(int(message_id))
                except Exception:
                    pass

            prize = giveaway.get("prize", "Prize")
            jump_url = message.jump_url if message else ""

            if not remaining_pool:
                giveaway["current_pending_winners"] = []
                unfilled_count = len(unclaimed)
                giveaway["unfilled_slots"] = giveaway.get("unfilled_slots", 0) + unfilled_count
                if claimed:
                    giveaway["status"] = GiveawayState.COMPLETED.value
                else:
                    giveaway["status"] = GiveawayState.NO_ELIGIBLE_ENTRANTS.value
                db.save_giveaway(mid_str, giveaway)
                audit_ledger.record_event(mid_str, "REROLL_FAILED", "SYSTEM", {
                    "reason": "Eligible pool exhausted",
                    "unfilled_slots": unfilled_count,
                    "claimed_count": len(claimed)
                })
                if channel:
                    await channel.send(f"⚠️ Unclaimed prize for **{prize}** expired, but no eligible replacement entrants remain.")
                # Notify host
                host_id = int(giveaway.get("host_id", 0))
                if guild and host_id:
                    try:
                        h_member = guild.get_member(host_id) or await guild.fetch_member(host_id)
                        if h_member:
                            await h_member.send(f"⚠️ **Giveaway Claim Timeout:** The claim for **{prize}** expired, and no eligible alternative entrants remain to reroll.")
                    except Exception:
                        pass
                return

            # Draw replacement cryptographically
            new_picks = cls.draw_cryptographic_winner(remaining_pool, len(unclaimed))
            unfilled_diff = len(unclaimed) - len(new_picks)
            if unfilled_diff > 0:
                giveaway["unfilled_slots"] = giveaway.get("unfilled_slots", 0) + unfilled_diff

            giveaway["current_pending_winners"] = new_picks
            giveaway["winners"].extend(new_picks)

            # Fresh claim window
            claim_dur = giveaway.get("claim_duration_seconds", 900)
            new_deadline = time.time() + claim_dur
            giveaway["claim_deadline"] = new_deadline
            giveaway["status"] = "AWAITING_CLAIM" if prior_status == "AWAITING_CLAIM" else GiveawayState.CLAIM_PENDING.value
            db.save_giveaway(mid_str, giveaway)

            audit_ledger.record_event(mid_str, "REROLLED", "SYSTEM", {
                "replacement_winners": new_picks,
                "new_deadline": new_deadline
            })

            mentions = ", ".join([f"<@{w}>" for w in new_picks])
            claim_view = GiveawayClaimView(mid_str)
            if channel:
                await channel.send(
                    f"🔄 **Replacement Winner Drawn!**\n"
                    f"The previous claim expired. Congratulations {mentions}! You are the new winner for **{prize}**!\n"
                    f"⏳ Claim Deadline: <t:{int(new_deadline)}:R>",
                    view=claim_view
                )

            # Notify new winners via DM
            if guild:
                for w in new_picks:
                    try:
                        w_member = guild.get_member(int(w)) or await guild.fetch_member(int(w))
                        if w_member and not getattr(w_member, "bot", False):
                            await w_member.send(
                                f"🔄 **You have been drawn as a replacement winner for {prize} in {guild.name}!**\n"
                                f"👉 Claim your prize here: {jump_url}\n"
                                f"⏳ Claim Deadline: <t:{int(new_deadline)}:R>"
                            )
                    except Exception:
                        pass

                # Notify host
                host_id = int(giveaway.get("host_id", 0))
                if host_id:
                    try:
                        h_member = guild.get_member(host_id) or await guild.fetch_member(host_id)
                        if h_member:
                            await h_member.send(
                                f"🔄 **Giveaway Rerolled:** Replacement winner(s) for your **{prize}** giveaway in **{guild.name}** have been selected: {mentions}!\n"
                                f"Link: {jump_url}"
                            )
                    except Exception:
                        pass

    @classmethod
    async def check_active_giveaways(cls, bot: commands.Bot):
        """Periodic background supervisor task checking giveaway timers and expired claim deadlines."""
        db = get_feature_db()
        now = time.time()
        for g in db.get_active_giveaways():
            mid = g.get("message_id")
            if not mid:
                continue
            # Check end time
            if g.get("end_time", 0) <= now and not g.get("ended", False) and not g.get("paused", False):
                await cls.finish_giveaway(bot, mid)

            # Check claim deadline
            elif g.get("ended", False) and g.get("claim_deadline_enabled", True) and g.get("status") in ("AWAITING_CLAIM", "CLAIM_PENDING", "REROLLING"):
                deadline = g.get("claim_deadline")
                if deadline and now > deadline:
                    await cls.process_expired_claim_reroll(bot, mid)

    @classmethod
    def generate_fairness_report(cls, message_id: str) -> Dict[str, Any]:
        """Generates comprehensive giveaway fairness report with audit verification."""
        db = get_feature_db()
        g = db.get_giveaway(message_id)
        if not g:
            return {"error": "Giveaway not found"}

        is_chain_valid, verified_count, chain_error = audit_ledger.verify_integrity(message_id)
        return {
            "giveaway_id": str(message_id),
            "prize": g.get("prize"),
            "host_id": g.get("host_id"),
            "closing_time": g.get("end_time"),
            "status": g.get("status", "Ended" if g.get("ended") else "Active"),
            "total_entries": len(g.get("entries", [])),
            "initial_winners": g.get("winners", [])[:g.get("winners_count", 1)],
            "claimed_winners": g.get("claimed_winners", []),
            "disqualified_winners": g.get("disqualified_winners", []),
            "current_pending": g.get("current_pending_winners", []),
            "unfilled_slots": g.get("unfilled_slots", 0),
            "claim_deadline_enabled": g.get("claim_deadline_enabled", True),
            "claim_deadline": g.get("claim_deadline"),
            "cryptographic_algorithm": "Python secrets.SystemRandom CSPRNG",
            "audit_ledger_status": {
                "valid": is_chain_valid,
                "verified_events": verified_count,
                "error": chain_error
            }
        }


# -----------------------------------------------------------------------------
# Authoritative Giveaway Execution Function
# -----------------------------------------------------------------------------
async def create_giveaway_execution(
    bot: Any,
    guild: discord.Guild,
    target_channel: discord.TextChannel,
    host_user: Any,
    prize: str,
    duration_str: str,
    winners_count: int = 1,
    claim_duration_seconds: int = 900,
    required_role_id: Optional[int] = None,
    db: Any = None,
    announcement_channel_id: Optional[int] = None
) -> Tuple[bool, Optional[discord.Message], Optional[str]]:
    """
    Authoritative giveaway creation engine.
    - Validates duration (>= 10s)
    - Validates bot permissions in target channel
    - Posts persistent GiveawayEntryView embed to target channel
    - Optionally posts announcement with jump link to dedicated announcement channel
    - Records state atomically in FeatureDatabase and SHA-256 audit ledger
    """
    if db is None:
        db = get_feature_db()

    seconds = parse_duration(duration_str)
    if not seconds or seconds < 10:
        return False, None, "Invalid duration. Duration must be at least 10 seconds (e.g. `10m`, `2h`, `1d`)."

    # Permission check for target channel
    if guild and hasattr(guild, "me") and guild.me:
        perms = target_channel.permissions_for(guild.me)
        if not (perms.send_messages and perms.embed_links):
            return False, None, f"I don't have permission to send messages and embed links in {target_channel.mention}!"

    num_w = max(1, min(20, int(winners_count or 1)))
    end_timestamp = time.time() + seconds

    embed = discord.Embed(
        title=f"🎉 GIVEAWAY: {prize}!",
        description=(
            f"Click **Enter Giveaway** below to participate!\n\n"
            f"**Winners:** `{num_w}`\n"
            f"**Ends:** <t:{int(end_timestamp)}:R> (<t:{int(end_timestamp)}:f>)\n"
            f"**Hosted by:** {host_user.mention}\n"
            f"**Mode:** Claim Deadline (15m window + automatic replacement rerolls)"
        ),
        color=0xf43f5e
    )
    embed.set_footer(text="Kazumi Giveaway System 🌸 • Cryptographically Fair")

    view = GiveawayEntryView("pending")
    try:
        msg = await target_channel.send(embed=embed, view=view)
    except Exception as e:
        logger.error(f"Failed to post giveaway message to {target_channel.id}: {e}")
        return False, None, f"Failed to post giveaway to {target_channel.mention}: {e}"

    # Dedicated Announcement Channel routing
    ann_ch_to_use = None
    if announcement_channel_id:
        ann_ch_to_use = guild.get_channel(int(announcement_channel_id))

    if not ann_ch_to_use and db and hasattr(db, "get_guild_settings") and guild:
        g_settings = db.get_guild_settings(guild.id)
        g_ann_id = g_settings.get("giveaway_announcement_channel_id")
        if g_ann_id:
            ann_ch_to_use = guild.get_channel(int(g_ann_id))

    if not ann_ch_to_use and guild:
        env_ann = os.environ.get("GIVEAWAY_ANNOUNCEMENT_CHANNEL_ID")
        if env_ann and env_ann.isdigit():
            ann_ch_to_use = guild.get_channel(int(env_ann))

    ann_msg = None
    if ann_ch_to_use and isinstance(ann_ch_to_use, discord.TextChannel) and ann_ch_to_use.id != target_channel.id:
        try:
            ann_embed = discord.Embed(
                title="📢 GIVEAWAY ANNOUNCEMENT!",
                description=(
                    f"🎉 A new giveaway has started in {target_channel.mention}!\n\n"
                    f"**Prize:** {prize}\n"
                    f"**Host:** {host_user.mention}\n"
                    f"**Winners:** `{num_w}`\n"
                    f"**Ends:** <t:{int(end_timestamp)}:R> (<t:{int(end_timestamp)}:f>)\n\n"
                    f"👉 **[Jump to Giveaway]({msg.jump_url})**"
                ),
                color=0x38bdf8
            )
            ann_embed.set_footer(text="Kazumi Giveaway Announcements 🌸")
            ann_msg = await ann_ch_to_use.send(embed=ann_embed)
        except Exception as ann_err:
            logger.warning(f"Could not post announcement to channel {ann_ch_to_use.id}: {ann_err}")

    ga_data = {
        "id": str(msg.id),
        "message_id": str(msg.id),
        "channel_id": str(target_channel.id),
        "guild_id": str(guild.id) if guild else "0",
        "host_id": str(host_user.id),
        "prize": prize,
        "winners_count": num_w,
        "winners": num_w,
        "end_time": end_timestamp,
        "required_role_id": str(required_role_id) if required_role_id else None,
        "entries": [],
        "eligible_entries": [],
        "winners_selected": [],
        "current_pending_winners": [],
        "claimed_winners": [],
        "disqualified_winners": [],
        "ended": False,
        "paused": False,
        "status": GiveawayState.ACTIVE.value,
        "claim_deadline_enabled": True,
        "claim_duration_seconds": claim_duration_seconds,
        "created_at": time.time(),
        "announcement_channel_id": str(ann_ch_to_use.id) if ann_msg else None,
        "announcement_message_id": str(ann_msg.id) if ann_msg else None,
        "draw_history": []
    }
    try:
        saved_ok = True
        if db:
            saved_ok = db.save_giveaway(str(msg.id), ga_data)
        if saved_ok is False:
            raise RuntimeError(f"Database persistence returned failure for giveaway {msg.id}")

        audit_ledger.record_event(str(msg.id), "CREATED", str(host_user.id), {
            "prize": prize,
            "duration": duration_str,
            "winners": num_w,
            "target_channel_id": str(target_channel.id),
            "announcement_channel_id": str(ann_ch_to_use.id) if ann_msg else None
        })
    except Exception as persist_err:
        logger.error(f"Failed to persist giveaway {msg.id} after sending Discord message: {persist_err}")
        # Roll back database record if saved
        if db and hasattr(db, "delete_giveaway"):
            try:
                db.delete_giveaway(str(msg.id))
            except Exception as db_rb_err:
                logger.error(f"Failed to roll back database record for orphaned giveaway {msg.id}: {db_rb_err}")

        # Clean up orphaned Discord messages
        try:
            await msg.delete()
        except Exception as del_err:
            logger.warning(f"Failed to delete orphaned giveaway message {msg.id} during rollback: {del_err}")
            try:
                for child in getattr(view, "children", []):
                    child.disabled = True
                await msg.edit(view=view)
            except Exception as edit_err:
                logger.warning(f"Failed to disable controls on orphaned giveaway message {msg.id}: {edit_err}")

        if ann_msg:
            try:
                await ann_msg.delete()
            except Exception as ann_del_err:
                logger.warning(f"Failed to delete orphaned announcement message {ann_msg.id}: {ann_del_err}")

        return False, None, f"Failed to persist giveaway record: {persist_err}"

    return True, msg, None


GiveawayManager.create_giveaway = staticmethod(create_giveaway_execution)


# -----------------------------------------------------------------------------
# Slash Commands Registration
# -----------------------------------------------------------------------------
def register_giveaway_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="giveaway", description="Create and manage secure, fair server giveaways 🎉")
    @app_commands.describe(
        action="Action (create, end, reroll, cancel, list, info, claim, audit)",
        duration="Duration for giveaway (e.g. 10m, 2h, 1d) [create]",
        prize="Prize description [create]",
        winners="Number of winners (default 1) [create]",
        claim_mode="Claim window mode ('deadline' for 24h countdown & reroll, 'no_deadline' for permanent claim)",
        channel="Target channel for announcement (default: current) [create]",
        required_role="Role required to participate (optional) [create]",
        message_id="Message ID of the giveaway (for end, reroll, cancel, info, claim, audit)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Create Giveaway", value="create"),
        app_commands.Choice(name="End Giveaway Early", value="end"),
        app_commands.Choice(name="Reroll Winners", value="reroll"),
        app_commands.Choice(name="Claim Prize", value="claim"),
        app_commands.Choice(name="Cancel Giveaway", value="cancel"),
        app_commands.Choice(name="List Giveaways", value="list"),
        app_commands.Choice(name="Giveaway Info", value="info"),
        app_commands.Choice(name="Fairness & Audit Report", value="audit")
    ])
    @app_commands.choices(claim_mode=[
        app_commands.Choice(name="Claim Deadline (24h Window + Auto-Reroll)", value="deadline"),
        app_commands.Choice(name="No Claim Deadline (Permanent)", value="no_deadline")
    ])
    async def slash_giveaway(
        interaction: discord.Interaction,
        action: app_commands.Choice[str],
        duration: Optional[str] = None,
        prize: Optional[str] = None,
        winners: Optional[int] = 1,
        claim_mode: Optional[app_commands.Choice[str]] = None,
        channel: Optional[discord.TextChannel] = None,
        required_role: Optional[discord.Role] = None,
        message_id: Optional[str] = None
    ):
        act = action.value

        # Handle user-facing Claim command without needing Manage Server
        if act == "claim":
            mid = message_id or (str(interaction.message.id) if interaction.message else "")
            if not mid:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway you won.", ephemeral=True)
                return

            g = db.get_giveaway(mid)
            if not g:
                await interaction.response.send_message("❌ Giveaway not found.", ephemeral=True)
                return

            uid = str(interaction.user.id)
            if uid not in g.get("current_pending_winners", g.get("winners", [])):
                await interaction.response.send_message("❌ You are not recorded as a drawn winner for this giveaway.", ephemeral=True)
                return

            g.setdefault("claimed_winners", []).append(uid)
            g["status"] = "CLAIMED"
            db.save_giveaway(mid, g)
            audit_ledger.record_event(mid, "CLAIMED", uid, {"prize": g.get("prize")})
            await interaction.response.send_message(f"🎉 Congratulations {interaction.user.mention}! Your claim for **{g.get('prize')}** is confirmed! 🌸")
            return

        # Administrative actions require Manage Server
        if not interaction.guild or not interaction.user.guild_permissions.manage_guild:
            await interaction.response.send_message("❌ You require **Manage Server** permission to manage giveaways.", ephemeral=True)
            return

        target_channel = channel or interaction.channel

        if act == "create":
            if not duration or not prize:
                await interaction.response.send_message("❌ Please specify both `duration` (e.g. `10m`, `2h`, `1d`) and `prize`.", ephemeral=True)
                return

            success, gw_msg, err = await create_giveaway_execution(
                bot=bot,
                guild=interaction.guild,
                target_channel=target_channel,
                host_user=interaction.user,
                prize=prize,
                duration_str=duration,
                winners_count=winners or 1,
                required_role_id=required_role.id if required_role else None,
                db=db
            )
            if not success:
                await interaction.response.send_message(f"❌ {err}", ephemeral=True)
                return
            await interaction.response.send_message(f"✅ Giveaway created in {target_channel.mention}!", ephemeral=True)

        elif act == "end":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            await GiveawayManager.finish_giveaway(bot, message_id.strip())
            await interaction.response.send_message("✅ Giveaway concluded.", ephemeral=True)

        elif act == "reroll":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            await GiveawayManager.process_expired_claim_reroll(bot, message_id.strip())
            await interaction.response.send_message("✅ Reroll executed.", ephemeral=True)

        elif act == "cancel":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            g = db.get_giveaway(message_id.strip())
            if g:
                g["ended"] = True
                g["status"] = "CANCELLED"
                db.save_giveaway(message_id.strip(), g)
                audit_ledger.record_event(message_id.strip(), "CANCELLED", str(interaction.user.id), {"reason": "Cancelled by moderator"})
            await interaction.response.send_message("✅ Giveaway cancelled safely.", ephemeral=True)

        elif act == "list":
            guild_giveaways = db.get_guild_giveaways(str(interaction.guild_id))
            if not guild_giveaways:
                await interaction.response.send_message("ℹ️ No giveaways recorded in this server.", ephemeral=True)
                return
            embed = discord.Embed(title=f"🎉 Giveaways • {interaction.guild.name}", color=0xf43f5e)
            for g in guild_giveaways[-8:]:
                mid = g.get("message_id", "?")
                prize_name = g.get("prize", "Gift")
                entries_cnt = len(g.get("entries", []))
                status = g.get("status", "Ended" if g.get("ended") else "Active")
                embed.add_field(name=f"🎁 {prize_name} (`{mid}`)", value=f"**Status:** `{status}` | **Entries:** `{entries_cnt}`", inline=False)
            await interaction.response.send_message(embed=embed)

        elif act == "info":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway.", ephemeral=True)
                return
            report = GiveawayManager.generate_fairness_report(message_id.strip())
            if "error" in report:
                await interaction.response.send_message(f"❌ {report['error']}", ephemeral=True)
                return
            embed = discord.Embed(title=f"🎉 Giveaway Info: {report['prize']}", color=0x38bdf8)
            embed.add_field(name="Giveaway ID", value=f"`{report['giveaway_id']}`", inline=True)
            embed.add_field(name="Status", value=f"**{report['status']}**", inline=True)
            embed.add_field(name="Total Entries", value=f"👥 **{report['total_entries']}**", inline=True)
            embed.add_field(name="Winners Picked", value=f"{len(report['initial_winners'])}", inline=True)
            embed.add_field(name="Claimed", value=f"{len(report['claimed_winners'])}", inline=True)
            if report.get("unfilled_slots", 0) > 0:
                embed.add_field(name="Unfilled Slots", value=f"⚠️ **{report['unfilled_slots']}**", inline=True)
            embed.add_field(name="Disqualified/Expired", value=f"{len(report['disqualified_winners'])}", inline=True)
            await interaction.response.send_message(embed=embed)

        elif act == "audit":
            if not message_id:
                await interaction.response.send_message("❌ Please provide the `message_id` of the giveaway to verify audit history.", ephemeral=True)
                return
            report = GiveawayManager.generate_fairness_report(message_id.strip())
            if "error" in report:
                await interaction.response.send_message(f"❌ {report['error']}", ephemeral=True)
                return

            audit_info = report["audit_ledger_status"]
            integrity_str = "✅ Verified (Chain intact)" if audit_info["valid"] else f"❌ Broken: {audit_info['error']}"

            embed = discord.Embed(title=f"🛡️ Giveaway Fairness & Audit Report • #{message_id}", color=0x10b981)
            embed.add_field(name="Prize", value=report["prize"], inline=True)
            embed.add_field(name="Status", value=f"**{report['status']}**", inline=True)
            embed.add_field(name="Claimed", value=f"{len(report['claimed_winners'])}", inline=True)
            if report.get("unfilled_slots", 0) > 0:
                embed.add_field(name="Unfilled Slots", value=f"⚠️ **{report['unfilled_slots']}**", inline=True)
            embed.add_field(name="Randomness Source", value=report["cryptographic_algorithm"], inline=True)
            embed.add_field(name="Hash Chain Integrity", value=integrity_str, inline=False)
            embed.add_field(name="Recorded Audit Events", value=f"`{audit_info['verified_events']}` events in immutable ledger", inline=True)
            embed.set_footer(text="Kazumi Append-Only SHA-256 Event Chain 🌸")
            await interaction.response.send_message(embed=embed)


# Alias for background supervisor functionality
GiveawaySupervisor = GiveawayManager

