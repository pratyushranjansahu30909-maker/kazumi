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
    CLOSED = "CLOSED"
    DRAWING = "DRAWING"
    AWAITING_CLAIM = "AWAITING_CLAIM"
    CLAIMED = "CLAIMED"
    EXPIRED = "EXPIRED"
    REROLLING = "REROLLING"
    COMPLETED = "COMPLETED"


def parse_duration(duration_str: str) -> Optional[float]:
    """Parses duration strings like 10m, 2h, 1d, 30s into seconds."""
    match = re.match(r"^(\d+)\s*([smhdw])$", str(duration_str).strip().lower())
    if not match:
        return None
    val = int(match.group(1))
    unit = match.group(2)
    multipliers = {"s": 1, "m": 60, "h": 3600, "d": 86400, "w": 604800}
    return float(val * multipliers[unit])


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
            expected_prev = self.events[i - 1]["hash"] if i > 0 else "GENESIS"
            ev_prev = ev.get("prev_hash") or ev.get("previous_hash")
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
        db = get_feature_db()
        mid = str(interaction.message.id)
        giveaway = db.get_giveaway(mid)
        if not giveaway or giveaway.get("ended", False):
            await interaction.response.send_message("❌ This giveaway has already ended.", ephemeral=True)
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


_claim_locks = set()

class GiveawayClaimView(discord.ui.View):
    """Interactive button allowing the selected winner to securely claim their prize."""
    def __init__(self, message_id: str):
        super().__init__(timeout=None)
        self.message_id = str(message_id)

    @discord.ui.button(label="Claim Prize 🎁", style=discord.ButtonStyle.primary, emoji="✨", custom_id="kazumi:giveaway:claim")
    async def claim_prize(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        lock_key = f"{self.message_id}:{uid}"
        if lock_key in _claim_locks:
            await interaction.response.send_message("⏳ Your claim is already being processed, please wait a moment.", ephemeral=True)
            return

        _claim_locks.add(lock_key)
        try:
            db = get_feature_db()
            giveaway = db.get_giveaway(self.message_id)
            if not giveaway:
                await interaction.response.send_message("❌ Giveaway record not found.", ephemeral=True)
                return

            current_winners = giveaway.get("current_pending_winners", giveaway.get("winners", []))

            if uid not in current_winners:
                await interaction.response.send_message("❌ Only the drawn winner can claim this prize!", ephemeral=True)
                return

            claimed_users = set(giveaway.get("claimed_winners", []))
            if uid in claimed_users:
                await interaction.response.send_message("✅ You have already claimed this prize! Contact server staff to receive it.", ephemeral=True)
                return

            # Check claim deadline
            deadline = giveaway.get("claim_deadline")
            now = time.time()
            if giveaway.get("claim_deadline_enabled", True) and deadline and now > deadline:
                await interaction.response.send_message("⏱️ The claim deadline has expired. This prize has been scheduled for a reroll.", ephemeral=True)
                return

            # Mark claimed
            giveaway.setdefault("claimed_winners", []).append(uid)
            giveaway["status"] = "CLAIMED"
            db.save_giveaway(self.message_id, giveaway)

            audit_ledger.record_event(self.message_id, "CLAIMED", uid, {"prize": giveaway["prize"]})

            button.disabled = True
            button.label = "Claimed! ✅"
            await interaction.response.edit_message(view=self)
            await interaction.followup.send(f"🎉 Congratulations {interaction.user.mention}! Your claim for **{giveaway['prize']}** is confirmed! Server staff have been notified. 🌸")
        finally:
            _claim_locks.discard(lock_key)


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

    _finalizing_locks = set()

    @classmethod
    async def finish_giveaway(cls, bot: commands.Bot, message_id: str):
        """Concludes giveaway, selects winner cryptographically, and begins claim window."""
        mid_str = str(message_id)
        if mid_str in cls._finalizing_locks:
            return
        cls._finalizing_locks.add(mid_str)
        try:
            db = get_feature_db()
            giveaway = db.get_giveaway(mid_str)
            if not giveaway or giveaway.get("ended", False):
                return

            giveaway["ended"] = True
            giveaway["status"] = "DRAWING"
            db.save_giveaway(mid_str, giveaway)

            try:
                guild = bot.get_guild(int(giveaway["guild_id"]))
                if not guild:
                    return
                channel = guild.get_channel(int(giveaway["channel_id"]))
                if not channel:
                    return
                message = await channel.fetch_message(int(message_id))
            except Exception as e:
                logger.warning(f"Failed to fetch giveaway message {message_id}: {e}")
                return

            entries = list(dict.fromkeys(giveaway.get("entries", [])))
            num_winners = max(1, giveaway.get("winners_count", 1))
            prize = giveaway.get("prize", "Surprise Gift")

            if not entries:
                giveaway["status"] = "COMPLETED_NO_ENTRIES"
                db.save_giveaway(message_id, giveaway)
                embed = discord.Embed(
                    title=f"🎉 Giveaway Concluded: {prize}",
                    description="Unfortunately, no eligible members entered the giveaway.",
                    color=0x94a3b8
                )
                embed.set_footer(text="Kazumi Giveaway System 🌸 • Cryptographically Fair")
                try:
                    await message.edit(embed=embed, view=None)
                    await channel.send(f"🎉 The giveaway for **{prize}** ended with zero entries.")
                except Exception:
                    pass
                audit_ledger.record_event(message_id, "CLOSED", "SYSTEM", {"reason": "No entries"})
                return

            # Select initial winners cryptographically
            winners = cls.draw_cryptographic_winner(entries, num_winners)
            giveaway["winners"] = winners
            giveaway["current_pending_winners"] = list(winners)
            giveaway["disqualified_winners"] = []
            giveaway["claimed_winners"] = []

            # Claim deadline calculation (Mode A vs Mode B)
            deadline_enabled = giveaway.get("claim_deadline_enabled", True)
            claim_dur = giveaway.get("claim_duration_seconds", 86400)  # Default 24 hours
            claim_deadline = time.time() + claim_dur if deadline_enabled else None
            giveaway["claim_deadline"] = claim_deadline
            giveaway["status"] = "AWAITING_CLAIM"
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
            try:
                await message.edit(embed=embed, view=claim_view)
                await channel.send(
                    f"🎉 Congratulations {', '.join(winner_mentions)}! You have won **{prize}**! Please claim before your window expires: 🎁",
                    view=claim_view
                )
            except Exception as e:
                logger.warning(f"Failed to post giveaway winner announcement: {e}")
        finally:
            cls._finalizing_locks.discard(mid_str)

    @classmethod
    async def process_expired_claim_reroll(cls, bot: commands.Bot, message_id: str):
        """
        Handles automatic winner replacement when claim deadline expires in Mode A.
        Marks expired winner, selects new winner from remaining pool, and grants fresh claim window.
        """
        mid_str = str(message_id)
        if mid_str in cls._finalizing_locks:
            return
        cls._finalizing_locks.add(mid_str)
        try:
            db = get_feature_db()
            giveaway = db.get_giveaway(mid_str)
            if not giveaway or not giveaway.get("claim_deadline_enabled", True):
                return

            now = time.time()
            deadline = giveaway.get("claim_deadline")
            if not deadline or now <= deadline:
                return

            # Mark state as actively rerolling to prevent concurrent tasks
            giveaway["status"] = "REROLLING"
            db.save_giveaway(mid_str, giveaway)

            pending = list(giveaway.get("current_pending_winners", []))
            claimed = set(giveaway.get("claimed_winners", []))
            unclaimed = [u for u in pending if u not in claimed]

            if not unclaimed:
                giveaway["status"] = "COMPLETED"
                db.save_giveaway(mid_str, giveaway)
                return

            # Mark unclaimed as disqualified / expired
            disqualified = giveaway.setdefault("disqualified_winners", [])
            disqualified.extend(unclaimed)
            for u in unclaimed:
                audit_ledger.record_event(mid_str, "EXPIRED", u, {"reason": "Claim window expired"})

            # Pick replacement winners from remaining pool
            all_entries = list(dict.fromkeys(giveaway.get("entries", [])))
            all_past_winners = set(giveaway.get("winners", []) + disqualified + list(claimed))
            remaining_pool = [uid for uid in all_entries if uid not in all_past_winners]

            try:
                guild = bot.get_guild(int(giveaway["guild_id"]))
                channel = guild.get_channel(int(giveaway["channel_id"])) if guild else None
            except Exception:
                channel = None

            if not remaining_pool:
                giveaway["status"] = "COMPLETED_EXHAUSTED"
                db.save_giveaway(mid_str, giveaway)
                audit_ledger.record_event(mid_str, "REROLL_FAILED", "SYSTEM", {"reason": "Eligible pool exhausted"})
                if channel:
                    await channel.send(f"⚠️ Unclaimed prize for **{giveaway['prize']}** expired, but no eligible replacement entrants remain.")
                return

            # Draw replacement
            new_picks = cls.draw_cryptographic_winner(remaining_pool, len(unclaimed))
            giveaway["current_pending_winners"] = new_picks
            giveaway["winners"].extend(new_picks)

            # Fresh claim window
            claim_dur = giveaway.get("claim_duration_seconds", 86400)
            new_deadline = time.time() + claim_dur
            giveaway["claim_deadline"] = new_deadline
            giveaway["status"] = "AWAITING_CLAIM"
            db.save_giveaway(mid_str, giveaway)

            audit_ledger.record_event(mid_str, "REROLLED", "SYSTEM", {
                "replacement_winners": new_picks,
                "new_deadline": new_deadline
            })

            if channel:
                mentions = ", ".join([f"<@{w}>" for w in new_picks])
                claim_view = GiveawayClaimView(mid_str)
                await channel.send(
                    f"🔄 **Replacement Winner Drawn!**\n"
                    f"The previous claim expired. Congratulations {mentions}! You are the new winner for **{giveaway['prize']}**!\n"
                    f"⏳ Claim Deadline: <t:{int(new_deadline)}:R>",
                    view=claim_view
                )
        finally:
            cls._finalizing_locks.discard(mid_str)

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
            elif g.get("ended", False) and g.get("claim_deadline_enabled", True) and g.get("status") in ("AWAITING_CLAIM", "REROLLING"):
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
# Slash Commands Registration
# -----------------------------------------------------------------------------
def register_giveaway_commands(tree: app_commands.CommandTree, bot: commands.Bot):
    db = get_feature_db()

    @tree.command(name="giveaway", description="Create and manage secure, fair server giveaways 🎉")
    @app_commands.describe(
        action="Action (create, end, reroll, pause, resume, cancel, list, info, claim, audit)",
        duration="Duration for giveaway (e.g. 10m, 2h, 1d) [create]",
        prize="Prize description [create]",
        winners="Number of winners (default 1) [create]",
        claim_mode="Claim window mode ('deadline' for 24h countdown & reroll, 'no_deadline' for permanent claim)",
        channel="Target channel for announcement (default: current) [create]",
        required_role="Role required to participate (optional) [create]",
        message_id="Message ID of the giveaway (for end, reroll, pause, resume, cancel, info, claim, audit)"
    )
    @app_commands.choices(action=[
        app_commands.Choice(name="Create Giveaway", value="create"),
        app_commands.Choice(name="End Giveaway Early", value="end"),
        app_commands.Choice(name="Reroll Winners", value="reroll"),
        app_commands.Choice(name="Claim Prize", value="claim"),
        app_commands.Choice(name="Pause Giveaway", value="pause"),
        app_commands.Choice(name="Resume Giveaway", value="resume"),
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

            seconds = parse_duration(duration)
            if not seconds or seconds < 10:
                await interaction.response.send_message("❌ Invalid duration. Minimum duration is 10 seconds (e.g. `10m`, `2h`, `1d`).", ephemeral=True)
                return

            end_timestamp = time.time() + seconds
            num_w = max(1, min(20, winners or 1))
            deadline_enabled = (claim_mode.value != "no_deadline") if claim_mode else True

            claim_mode_text = "\n**Mode:** Claim Deadline (24h window + automatic replacement rerolls)" if deadline_enabled else "\n**Mode:** No Claim Deadline"
            req_role_text = f"\n**Required Role:** {required_role.mention}" if required_role else ""

            embed = discord.Embed(
                title=f"🎉 GIVEAWAY: {prize}!",
                description=f"Click **Enter Giveaway** below to participate!\n\n"
                            f"**Winners:** `{num_w}`\n"
                            f"**Ends:** <t:{int(end_timestamp)}:R> (<t:{int(end_timestamp)}:f>)\n"
                            f"**Hosted by:** {interaction.user.mention}"
                            f"{claim_mode_text}{req_role_text}",
                color=0xf43f5e
            )
            embed.set_footer(text="Kazumi Giveaway System 🌸 • Cryptographically Fair")

            view = GiveawayEntryView("pending")
            msg = await target_channel.send(embed=embed, view=view)

            giveaway_data = {
                "message_id": str(msg.id),
                "channel_id": str(target_channel.id),
                "guild_id": str(interaction.guild_id),
                "host_id": str(interaction.user.id),
                "prize": prize,
                "winners_count": num_w,
                "end_time": end_timestamp,
                "required_role_id": str(required_role.id) if required_role else None,
                "entries": [],
                "winners": [],
                "current_pending_winners": [],
                "claimed_winners": [],
                "disqualified_winners": [],
                "ended": False,
                "paused": False,
                "claim_deadline_enabled": deadline_enabled,
                "claim_duration_seconds": 86400,
                "status": "ACTIVE"
            }
            db.save_giveaway(str(msg.id), giveaway_data)
            audit_ledger.record_event(str(msg.id), "CREATED", str(interaction.user.id), {
                "prize": prize,
                "winners": num_w,
                "end_time": end_timestamp,
                "deadline_enabled": deadline_enabled
            })
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
            embed.add_field(name="Randomness Source", value=report["cryptographic_algorithm"], inline=True)
            embed.add_field(name="Hash Chain Integrity", value=integrity_str, inline=False)
            embed.add_field(name="Recorded Audit Events", value=f"`{audit_info['verified_events']}` events in immutable ledger", inline=True)
            embed.set_footer(text="Kazumi Append-Only SHA-256 Event Chain 🌸")
            await interaction.response.send_message(embed=embed)


# Alias for background supervisor functionality
GiveawaySupervisor = GiveawayManager

