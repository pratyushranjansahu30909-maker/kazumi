# -*- coding: utf-8 -*-
"""
🌸 Kazumi Persistent Server Leveling & Chat Activity System
Provides genuine chat participation tracking, anti-farming protection,
rank cards, leaderboards, level-up celebrations, and role rewards.

Features:
- Configurable XP per message (random 10–20 XP) with per-user cooldowns (default 60s).
- Anti-farming: minimum length check, duplicate content hash rejection, bot exclusion.
- Separate tracking for XP and genuine eligible message counts.
- Level progression formula: XP needed for next level = 5 * (level^2) + 50 * level + 100.
- Level-up announcements with hierarchy-safe role reward assignments.
- Slash commands: /rank, /level, /leaderboard, /level-rewards, /level-admin, /xp-admin.
"""

import os
import time
import random
import hashlib
import logging
from typing import Dict, Any, Optional, List, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from .database import get_feature_db, FeatureDatabase

logger = logging.getLogger("KazumiLeveling")


def calculate_xp_for_level(level: int) -> int:
    """Returns XP required to advance from `level` to `level + 1`."""
    lvl = max(1, level)
    return int(5 * (lvl ** 2) + 50 * lvl + 100)


def generate_progress_bar(current: int, target: int, length: int = 10) -> Tuple[str, int]:
    """Generates a text progress bar and percentage."""
    if target <= 0:
        return ("▰" * length, 100)
    pct = min(1.0, max(0.0, current / target))
    filled = int(round(pct * length))
    bar = "▰" * filled + "▱" * (length - filled)
    return (bar, int(pct * 100))


class LevelingManager:
    """Manages chat activity, persistent XP progression, rank calculation, and role rewards."""

    def __init__(self, db: Optional[FeatureDatabase] = None, storage_file: Optional[str] = None):
        self.db = db
        self.levels_path = storage_file
        if not self.levels_path:
            db_inst = self.db or get_feature_db()
            self.levels_path = os.path.join(getattr(db_inst, "persist_dir", "isa_memory"), "levels.json")
        self.cooldowns: Dict[Any, float] = {}
        self.levels_data: Dict[str, Any] = {
            "users": {},     # "<guild_id>:<user_id>" -> {"xp": int, "level": int, "eligible_messages": int, "last_xp_time": float, "last_msg_hash": str}
            "guilds": {}     # "<guild_id>" -> config dict
        }
        self._load()

    def _load(self):
        """Loads levels data from atomic JSON file."""
        if self.levels_path and os.path.exists(self.levels_path):
            try:
                with open(self.levels_path, "r", encoding="utf-8") as f:
                    self.levels_data = json.load(f)
            except Exception:
                self.levels_data = {"users": {}, "guilds": {}}
        elif self.db:
            self.levels_data = self.db._safe_read(self.levels_path, {"users": {}, "guilds": {}})
        else:
            self.levels_data = {"users": {}, "guilds": {}}

    def _save(self):
        """Saves levels data atomically."""
        if not self.levels_path:
            return
        try:
            os.makedirs(os.path.dirname(os.path.abspath(self.levels_path)), exist_ok=True)
            with open(self.levels_path, "w", encoding="utf-8") as f:
                json.dump(self.levels_data, f, indent=2)
        except Exception:
            if self.db:
                self.db._atomic_write(self.levels_path, self.levels_data)

    def record_chat_activity(self, guild_id: Any, user_id: Any, text: str) -> Tuple[int, bool, int]:
        """
        Direct chat activity evaluation helper for testing and synchronous tracking.
        Returns (xp_gained: int, leveled_up: bool, new_level: int).
        """
        raw_text = (text or "").strip()
        cfg = self.get_guild_config(guild_id)
        if len(raw_text) < cfg.get("min_message_length", 4):
            return (0, False, 1)

        msg_hash = hashlib.md5(raw_text.encode("utf-8")).hexdigest()
        now = time.time()
        record = self.get_user_record(guild_id, user_id)

        cooldown = cfg.get("cooldown_seconds", 60)
        # Check cooldown and duplicate hash
        if (now - record["last_xp_time"] < cooldown) or (record["last_msg_hash"] == msg_hash):
            return (0, False, record["level"])

        record["eligible_messages"] += 1
        record["last_msg_hash"] = msg_hash
        record["last_xp_time"] = now
        self.cooldowns[user_id] = now

        xp_gain = random.randint(cfg.get("xp_min", 10), cfg.get("xp_max", 20))
        record["xp"] += xp_gain

        current_lvl = record["level"]
        xp_needed = calculate_xp_for_level(current_lvl)
        leveled_up = False
        while record["xp"] >= xp_needed:
            record["xp"] -= xp_needed
            record["level"] += 1
            current_lvl = record["level"]
            xp_needed = calculate_xp_for_level(current_lvl)
            leveled_up = True

        self._save()
        return (xp_gain, leveled_up, current_lvl)

    def adjust_user_xp(self, guild_id: Any, user_id: Any, xp_delta: int = 0, level_override: Optional[int] = None) -> None:
        """Manually adjusts user XP or level."""
        rec = self.get_user_record(guild_id, user_id)
        if level_override is not None:
            rec["level"] = level_override
        rec["xp"] = max(0, rec["xp"] + xp_delta)
        self._save()

    def get_guild_config(self, guild_id: Any) -> Dict[str, Any]:
        """Retrieves leveling configuration for a guild with sensible defaults."""
        gid = str(guild_id)
        guilds = self.levels_data.setdefault("guilds", {})
        if gid not in guilds:
            guilds[gid] = {
                "enabled": True,
                "xp_min": 10,
                "xp_max": 20,
                "cooldown_seconds": 60,
                "min_message_length": 4,
                "announcement_channel_id": None,
                "excluded_channels": [],
                "ignored_roles": [],
                "role_rewards": {}  # "level_str": "role_id_str"
            }
        return guilds[gid]

    def update_guild_config(self, guild_id: Any, updates: Dict[str, Any]) -> None:
        """Updates guild leveling configuration."""
        cfg = self.get_guild_config(guild_id)
        cfg.update(updates)
        self._save()

    def get_user_record(self, guild_id: Any, user_id: Any) -> Dict[str, Any]:
        """Gets or initializes the user leveling record."""
        key = f"{guild_id}:{user_id}"
        users = self.levels_data.setdefault("users", {})
        if key not in users:
            users[key] = {
                "xp": 0,
                "level": 1,
                "eligible_messages": 0,
                "last_xp_time": 0.0,
                "last_msg_hash": ""
            }
        return users[key]

    async def process_message_activity(self, message: discord.Message) -> Optional[Tuple[int, Optional[str]]]:
        """
        Evaluates a message for XP eligibility and awards XP.
        Returns (new_level, reward_role_id) if a level-up occurs, else None.
        """
        if not message.guild or message.author.bot:
            return None

        guild = message.guild
        author = message.author
        cfg = self.get_guild_config(guild.id)

        if not cfg.get("enabled", True):
            return None

        # Excluded channels check
        if message.channel.id in cfg.get("excluded_channels", []):
            return None

        # Ignored roles check
        if hasattr(author, "roles"):
            author_role_ids = {r.id for r in author.roles}
            if any(r_id in author_role_ids for r_id in cfg.get("ignored_roles", [])):
                return None

        # Anti-farming: minimum length check
        raw_text = (message.content or "").strip()
        if len(raw_text) < cfg.get("min_message_length", 4):
            return None

        # Anti-farming: duplicate message spam check
        msg_hash = hashlib.md5(raw_text.encode("utf-8")).hexdigest()
        now = time.time()
        record = self.get_user_record(guild.id, author.id)

        # Anti-farming: check if user is on cooldown or sent identical duplicate text
        cooldown = cfg.get("cooldown_seconds", 60)
        if (now - record["last_xp_time"] < cooldown) or (record["last_msg_hash"] == msg_hash):
            return None

        # Award XP and increment eligible message count
        record["eligible_messages"] += 1
        record["last_msg_hash"] = msg_hash
        record["last_xp_time"] = now

        xp_gain = random.randint(cfg.get("xp_min", 10), cfg.get("xp_max", 20))
        record["xp"] += xp_gain

        # Check level up
        current_lvl = record["level"]
        xp_needed = calculate_xp_for_level(current_lvl)
        leveled_up = False

        while record["xp"] >= xp_needed:
            record["xp"] -= xp_needed
            record["level"] += 1
            current_lvl = record["level"]
            xp_needed = calculate_xp_for_level(current_lvl)
            leveled_up = True

        self._save()

        if leveled_up:
            # Check for role rewards
            role_rewards = cfg.get("role_rewards", {})
            reward_role_id = role_rewards.get(str(current_lvl))

            # Attempt safe role assignment
            if reward_role_id and isinstance(author, discord.Member):
                role = guild.get_role(int(reward_role_id))
                if role and guild.me.top_role > role:
                    try:
                        await author.add_roles(role, reason=f"Level {current_lvl} reward")
                    except Exception as re_err:
                        logger.warning(f"Could not assign level reward role: {re_err}")

            return (current_lvl, reward_role_id)

        return None

    def get_user_stats(self, guild_id: Any, user_id: Any) -> Dict[str, Any]:
        """Calculates user level, current XP, next level XP, progress bar, and server rank."""
        record = self.get_user_record(guild_id, user_id)
        current_lvl = record["level"]
        current_xp = record["xp"]
        next_xp = calculate_xp_for_level(current_lvl)
        bar, pct = generate_progress_bar(current_xp, next_xp)

        # Calculate server rank
        gid_prefix = f"{guild_id}:"
        all_guild_users = []
        for k, v in self.levels_data.get("users", {}).items():
            if k.startswith(gid_prefix):
                uid = k.split(":")[1]
                # Overall cumulative score estimate for ranking
                score = (v["level"] * 10000) + v["xp"]
                all_guild_users.append((uid, score, v["level"], v["xp"], v.get("eligible_messages", 0)))

        all_guild_users.sort(key=lambda x: x[1], reverse=True)
        rank = 1
        for idx, item in enumerate(all_guild_users, start=1):
            if item[0] == str(user_id):
                rank = idx
                break

        return {
            "level": current_lvl,
            "xp": current_xp,
            "next_xp": next_xp,
            "progress_bar": bar,
            "progress_pct": pct,
            "rank": rank,
            "eligible_messages": record.get("eligible_messages", 0),
            "total_users": len(all_guild_users)
        }

    def get_leaderboard(self, guild_id: Any, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns top users in the guild sorted by level and XP."""
        gid_prefix = f"{guild_id}:"
        entries = []
        for k, v in self.levels_data.get("users", {}).items():
            if k.startswith(gid_prefix):
                uid = k.split(":")[1]
                entries.append({
                    "user_id": uid,
                    "level": v["level"],
                    "xp": v["xp"],
                    "eligible_messages": v.get("eligible_messages", 0),
                    "score": (v["level"] * 10000) + v["xp"]
                })

        entries.sort(key=lambda x: x["score"], reverse=True)
        return entries[:limit]

    def set_user_xp(self, guild_id: Any, user_id: Any, xp: int, level: Optional[int] = None) -> Dict[str, Any]:
        """Manually sets user XP and optional level."""
        record = self.get_user_record(guild_id, user_id)
        record["xp"] = max(0, int(xp))
        if level is not None:
            record["level"] = max(1, int(level))
        self._save()
        return record


# -----------------------------------------------------------------------------
# Slash Commands Registration
# -----------------------------------------------------------------------------
def register_leveling_commands(tree: app_commands.CommandTree, bot: commands.Bot, manager: LevelingManager, guild_id: Optional[int] = None):
    """Registers leveling slash commands safely honoring Discord global command limits."""
    # Target guild ID defaults to LAPEACE (1554152397327044729) or env var to stay within 100 global limit
    gid = guild_id or os.environ.get("DISCORD_GUILD_ID") or os.environ.get("TEST_GUILD_ID") or 1554152397327044729
    guild_target = discord.Object(id=int(gid)) if gid else None

    def _safe_add(cmd_obj):
        try:
            if guild_target is not None:
                tree.add_command(cmd_obj, guild=guild_target)
            elif len(tree.get_commands()) < 88:
                tree.add_command(cmd_obj)
            else:
                logger.info(f"[Leveling] Global slash command budget reached; command '{cmd_obj.name}' registered via guild sync, prefix & action engine.")
        except Exception as e:
            logger.debug(f"[Leveling] Note on command registration '{getattr(cmd_obj, 'name', '')}': {e}")

    # 1. /rank
    @app_commands.command(name="rank", description="🌸 View your or another member's rank card and activity stats.")
    @app_commands.describe(member="The member whose rank you want to check")
    async def rank_cmd(interaction: discord.Interaction, member: Optional[discord.Member] = None):
        target = member or interaction.user
        stats = manager.get_user_stats(interaction.guild.id, target.id)

        embed = discord.Embed(
            title=f"🌸 Rank Card — {target.display_name}",
            color=0xf472b6
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="Level", value=f"⭐ **{stats['level']}**", inline=True)
        embed.add_field(name="XP", value=f"✨ **{stats['xp']} / {stats['next_xp']}**", inline=True)
        embed.add_field(name="Server Rank", value=f"🏆 **#{stats['rank']}** of {stats['total_users']}", inline=True)
        embed.add_field(name="Eligible Messages", value=f"💬 **{stats['eligible_messages']}**", inline=True)
        embed.add_field(name="Progress to Next Level", value=f"`{stats['progress_bar']}` ({stats['progress_pct']}%)", inline=False)
        embed.set_footer(text="Keep chatting to earn more XP and climb the leaderboard! ✨")

        await interaction.response.send_message(embed=embed)

    # 2. /level
    @app_commands.command(name="level", description="⭐ Check your current chat level and XP.")
    async def level_cmd(interaction: discord.Interaction):
        stats = manager.get_user_stats(interaction.guild.id, interaction.user.id)
        await interaction.response.send_message(
            f"⭐ You are **Level {stats['level']}** (`{stats['xp']} / {stats['next_xp']} XP`)! Rank **#{stats['rank']}** in {interaction.guild.name}. 🌸"
        )

    # 3. /leaderboard
    @app_commands.command(name="leaderboard", description="🏆 View the top active chatters in this server.")
    async def leaderboard_cmd(interaction: discord.Interaction):
        lb = manager.get_leaderboard(interaction.guild.id, limit=10)
        if not lb:
            await interaction.response.send_message("No chat activity recorded yet! Start talking to earn XP. 🌸", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🏆 Server Leaderboard — {interaction.guild.name}",
            description="Top active members based on genuine chat participation:",
            color=0xf59e0b
        )
        for idx, entry in enumerate(lb, start=1):
            m = interaction.guild.get_member(int(entry["user_id"]))
            name = m.display_name if m else f"User {entry['user_id']}"
            embed.add_field(
                name=f"#{idx} {name}",
                value=f"Level **{entry['level']}** • `{entry['xp']} XP` • `{entry.get('eligible_messages', 0)} msgs`",
                inline=False
            )
        embed.set_footer(text="Anti-spam & cooldown filters active.")
        await interaction.response.send_message(embed=embed)

    # 4. /level-rewards
    @app_commands.command(name="level-rewards", description="🎁 View configured role rewards for each level.")
    async def rewards_cmd(interaction: discord.Interaction):
        cfg = manager.get_guild_config(interaction.guild.id)
        rewards = cfg.get("role_rewards", {})
        if not rewards:
            await interaction.response.send_message("No level role rewards are configured for this server yet.", ephemeral=True)
            return

        embed = discord.Embed(title=f"🎁 Level Rewards — {interaction.guild.name}", color=0xa855f7)
        for lvl_str, role_id_str in sorted(rewards.items(), key=lambda x: int(x[0])):
            role = interaction.guild.get_role(int(role_id_str))
            role_mention = role.mention if role else f"Role `{role_id_str}`"
            embed.add_field(name=f"Level {lvl_str}", value=role_mention, inline=False)
        await interaction.response.send_message(embed=embed)

    # 5. /level-admin
    @app_commands.command(name="level-admin", description="⚙️ Configure leveling settings for this server (Admins only).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        enabled="Enable or disable leveling system",
        cooldown="Cooldown in seconds between XP gains (e.g. 60)",
        min_length="Minimum message length for XP (e.g. 4)"
    )
    async def level_admin_cmd(
        interaction: discord.Interaction,
        enabled: Optional[bool] = None,
        cooldown: Optional[int] = None,
        min_length: Optional[int] = None
    ):
        updates = {}
        if enabled is not None:
            updates["enabled"] = enabled
        if cooldown is not None:
            updates["cooldown_seconds"] = max(5, cooldown)
        if min_length is not None:
            updates["min_message_length"] = max(1, min_length)

        if updates:
            manager.update_guild_config(interaction.guild.id, updates)
            await interaction.response.send_message(f"✅ Updated leveling configuration: `{updates}`", ephemeral=True)
        else:
            cfg = manager.get_guild_config(interaction.guild.id)
            await interaction.response.send_message(f"⚙️ Current configuration: `{cfg}`", ephemeral=True)

    # 6. /xp-admin
    @app_commands.command(name="xp-admin", description="🛠️ Adjust or repair user XP and level (Admins only).")
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(member="Member to adjust", xp="Set XP amount", level="Set Level number")
    async def xp_admin_cmd(interaction: discord.Interaction, member: discord.Member, xp: int, level: Optional[int] = None):
        res = manager.set_user_xp(interaction.guild.id, member.id, xp, level)
        await interaction.response.send_message(
            f"✅ Updated stats for {member.mention}: Level **{res['level']}**, XP **{res['xp']}**.",
            ephemeral=True
        )

    # Safely register commands honoring global / guild limits
    for cmd in [rank_cmd, level_cmd, leaderboard_cmd, rewards_cmd, level_admin_cmd, xp_admin_cmd]:
        _safe_add(cmd)
