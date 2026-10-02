"""
Natural Language Intent Router for Kazumi.
Parses natural language requests for Music, Moderation, and Giveaways,
enforcing strict permissions, ambiguity resolution, and companion personality.
"""

import re
import time
import logging
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timezone

import discord

from .permissions import PermissionService
from .giveaways import parse_duration

logger = logging.getLogger("KazumiIntentRouter")


class NaturalIntentRouter:
    """
    Translates conversational Discord messages into safe, authorized bot actions.
    Flow: Normalization -> Intent Detection -> Entity Extraction -> Perms -> Execution -> Response
    """

    def __init__(self, bot, features_dict: dict):
        self.bot = bot
        self.features = features_dict
        self.db = features_dict.get("db")
        self.permissions = PermissionService()

    def normalize(self, text: str) -> str:
        """Strip conversational filler and normalize whitespace."""
        clean = text.strip()
        # Remove bot mentions
        clean = re.sub(r"<@!?\d+>", "", clean)
        # Strip greeting & Kazumi address
        clean = re.sub(r"^(?:hey|hi|hello|yo|dear)?\s*kazumi\b[:,]?", "", clean, flags=re.IGNORECASE)
        # Strip conversational courtesies
        clean = re.sub(r"\b(?:please|can you|could you|would you mind|go ahead and)\b", "", clean, flags=re.IGNORECASE)
        clean = re.sub(r"\s+", " ", clean).strip()
        return clean

    def detect_intent(self, text: str, message: discord.Message) -> Optional[Dict[str, Any]]:
        """
        Extracts intent, category, and entities from normalized text.
        Returns None if message is purely conversational.
        """
        raw_norm = self.normalize(text)
        lower = raw_norm.lower()

        # =====================================================================
        # 1. MUSIC INTENTS
        # =====================================================================
        # Play intent: "play [song/query]", "play some music", "put on some jazz"
        play_match = re.search(r"^(?:play|queue up|put on)\s+(.+)$", lower)
        if play_match:
            query = play_match.group(1).strip()
            # If query is just "music", "some music", "a song"
            if query in {"music", "some music", "a song", "something"}:
                query = "relaxing lofi hip hop beats"
            return {"category": "music", "action": "play", "query": query}

        # Music playback controls
        if re.search(r"^(?:pause|pause music|pause playback|pause the song)$", lower):
            return {"category": "music", "action": "pause"}

        if re.search(r"^(?:resume|resume music|resume playback|unpause)$", lower):
            return {"category": "music", "action": "resume"}

        if re.search(r"^(?:skip|skip song|skip this song|next song)$", lower):
            return {"category": "music", "action": "skip"}

        if re.search(r"^(?:stop|stop music|stop playback|clear queue and stop)$", lower):
            return {"category": "music", "action": "stop"}

        if re.search(r"^(?:queue|show queue|show me the queue|what'?s in the queue|view queue)$", lower):
            return {"category": "music", "action": "queue"}

        if re.search(r"^(?:now playing|what song is playing|nowplaying|current song)$", lower):
            return {"category": "music", "action": "nowplaying"}

        if re.search(r"^(?:shuffle|shuffle queue|shuffle the queue)$", lower):
            return {"category": "music", "action": "shuffle"}

        if re.search(r"^(?:loop|loop song|loop this song|repeat song|repeat track)$", lower):
            return {"category": "music", "action": "loop"}

        if re.search(r"^(?:play previous|previous song|previous track|go back)$", lower):
            return {"category": "music", "action": "previous"}

        if re.search(r"^(?:leave voice|leave call|disconnect|leave the voice channel)$", lower):
            return {"category": "music", "action": "disconnect"}

        vol_match = re.search(r"^(?:set volume to|volume to|volume)\s+(\d+)(?:%|\s*percent)?$", lower)
        if vol_match:
            return {"category": "music", "action": "volume", "volume": int(vol_match.group(1))}

        # =====================================================================
        # 2. MODERATION INTENTS
        # =====================================================================
        # Warn intent: "warn @user [reason]", "warn [id] for [reason]"
        warn_match = re.search(r"^warn\s+(?:<@!?(\d+)>|(\d+)|([^\s]+))(?:\s+(?:for\s+)?(.+))?$", lower)
        if warn_match:
            target_str = warn_match.group(1) or warn_match.group(2) or warn_match.group(3)
            reason = warn_match.group(4) or "No reason provided"
            return {
                "category": "moderation",
                "action": "warn",
                "target_raw": target_str,
                "reason": reason
            }

        # Timeout / Mute intent: "timeout @user for 10m", "mute @user 1h [reason]"
        timeout_match = re.search(r"^(?:timeout|mute)\s+(?:<@!?(\d+)>|(\d+)|([^\s]+))(?:\s+for\s+|\s+)(\d+[smhdwy])(?:\s+(?:for\s+)?(.+))?$", lower)
        if timeout_match:
            target_str = timeout_match.group(1) or timeout_match.group(2) or timeout_match.group(3)
            dur_str = timeout_match.group(4)
            reason = timeout_match.group(5) or "No reason provided"
            return {
                "category": "moderation",
                "action": "timeout",
                "target_raw": target_str,
                "duration": dur_str,
                "reason": reason
            }

        # Untimeout / Unmute intent
        untimeout_match = re.search(r"^(?:untimeout|unmute)\s+(?:<@!?(\d+)>|(\d+)|([^\s]+))$", lower)
        if untimeout_match:
            target_str = untimeout_match.group(1) or untimeout_match.group(2) or untimeout_match.group(3)
            return {"category": "moderation", "action": "untimeout", "target_raw": target_str}

        # Kick intent: "kick @user [reason]"
        kick_match = re.search(r"^kick\s+(?:<@!?(\d+)>|(\d+)|([^\s]+))(?:\s+(?:for\s+)?(.+))?$", lower)
        if kick_match:
            target_str = kick_match.group(1) or kick_match.group(2) or kick_match.group(3)
            reason = kick_match.group(4) or "No reason provided"
            return {
                "category": "moderation",
                "action": "kick",
                "target_raw": target_str,
                "reason": reason
            }

        # Ban intent: "ban @user [reason]"
        ban_match = re.search(r"^ban\s+(?:<@!?(\d+)>|(\d+)|([^\s]+))(?:\s+(?:for\s+)?(.+))?$", lower)
        if ban_match:
            target_str = ban_match.group(1) or ban_match.group(2) or ban_match.group(3)
            reason = ban_match.group(4) or "No reason provided"
            return {
                "category": "moderation",
                "action": "ban",
                "target_raw": target_str,
                "reason": reason
            }

        # Lock channel intent: "lock this channel", "lockdown channel", "lock channel"
        if re.search(r"^(?:lock this channel|lock channel|lockdown channel|lockdown)$", lower):
            return {"category": "moderation", "action": "lock"}

        # Unlock channel intent: "unlock this channel", "unlock channel"
        if re.search(r"^(?:unlock this channel|unlock channel|lift lockdown)$", lower):
            return {"category": "moderation", "action": "unlock"}

        # Purge messages intent: "purge 20 messages", "clear 10 messages"
        purge_match = re.search(r"^(?:purge|clear)\s+(\d+)(?:\s+messages?)?$", lower)
        if purge_match:
            return {"category": "moderation", "action": "purge", "amount": int(purge_match.group(1))}

        # Slowmode intent: "set slowmode to 10s", "enable slowmode 5s", "turn off slowmode"
        if re.search(r"^(?:turn off slowmode|disable slowmode)$", lower):
            return {"category": "moderation", "action": "slowmode", "seconds": 0}
        sm_match = re.search(r"^(?:set slowmode to|slowmode)\s+(\d+)(?:s|seconds?)?$", lower)
        if sm_match:
            return {"category": "moderation", "action": "slowmode", "seconds": int(sm_match.group(1))}

        # Spam protection / AutoMod intent: "enable spam protection", "enable automod"
        if re.search(r"^(?:enable|turn on)\s+(?:spam protection|automod)$", lower):
            return {"category": "moderation", "action": "automod", "enable": True}
        if re.search(r"^(?:disable|turn off)\s+(?:spam protection|automod)$", lower):
            return {"category": "moderation", "action": "automod", "enable": False}

        # =====================================================================
        # 3. GIVEAWAY INTENTS
        # =====================================================================
        # Create giveaway: "start a giveaway for 24 hours", "start a giveaway for [prize] for [time]"
        ga_create_1 = re.search(r"^(?:start|create)\s+a?\s*giveaway\s+(?:for\s+)?(\d+[smhdwy])\s+(?:for\s+)?(.+)$", lower)
        if ga_create_1:
            return {
                "category": "giveaway",
                "action": "create",
                "duration": ga_create_1.group(1),
                "prize": ga_create_1.group(2).strip()
            }
        ga_create_2 = re.search(r"^(?:start|create)\s+a?\s*giveaway\s+(?:for\s+)?(.+)\s+for\s+(\d+[smhdwy])$", lower)
        if ga_create_2:
            return {
                "category": "giveaway",
                "action": "create",
                "prize": ga_create_2.group(1).strip(),
                "duration": ga_create_2.group(2)
            }
        ga_create_simple = re.search(r"^(?:start|create)\s+a?\s*giveaway\s+for\s+(\d+[smhdwy])$", lower)
        if ga_create_simple:
            return {
                "category": "giveaway",
                "action": "create",
                "duration": ga_create_simple.group(1),
                "prize": "Mystery Surprise Prize 🎁"
            }

        # End giveaway: "end the giveaway", "end giveaway"
        if re.search(r"^(?:end the giveaway|end giveaway|finish giveaway)$", lower):
            return {"category": "giveaway", "action": "end"}

        # Reroll giveaway: "reroll the giveaway", "reroll giveaway"
        if re.search(r"^(?:reroll the giveaway|reroll giveaway|pick a new winner)$", lower):
            return {"category": "giveaway", "action": "reroll"}

        # Giveaway info / list: "how many people entered the giveaway?", "show giveaways", "list giveaways"
        if re.search(r"^(?:how many people entered the giveaway\??|giveaway entries\??|list giveaways|show giveaways|giveaway status)$", lower):
            return {"category": "giveaway", "action": "list"}

        # No action intent detected -> Standard conversation flow
        return None

    def _resolve_target_member(self, guild: discord.Guild, target_raw: str, message: discord.Message) -> Tuple[Optional[discord.Member], bool]:
        """Resolves target member from mentions or ID string. Returns (member, is_ambiguous)."""
        # First check explicit mentions (excluding the bot itself)
        user_mentions = [m for m in message.mentions if m.id != self.bot.user.id] if self.bot.user else message.mentions
        if len(user_mentions) == 1:
            return user_mentions[0], False
        elif len(user_mentions) > 1:
            return None, True  # Ambiguous!

        # Try parsing target_raw
        if target_raw:
            clean_id = re.sub(r"[<@!>]", "", target_raw)
            if clean_id.isdigit():
                member = guild.get_member(int(clean_id))
                if member:
                    return member, False
            # Check by username or display_name
            for m in guild.members:
                if m.name.lower() == target_raw.lower() or m.display_name.lower() == target_raw.lower():
                    return m, False

        return None, True

    def _is_unhinged_active(self, guild_id: Optional[int], user_id: int) -> bool:
        """Checks if unhinged roast mode is enabled for this server or user."""
        if not self.db:
            return False
        if self.db.is_user_roast_opted_out(user_id):
            return False
        if guild_id:
            g_mode = self.db.get_guild_settings(str(guild_id)).get("roast_mode", "normal")
            if g_mode == "unhinged":
                return True
        return False

    async def execute_intent(
        self,
        intent: Dict[str, Any],
        message: discord.Message
    ) -> Tuple[bool, Optional[str], Optional[discord.Embed]]:
        """
        Executes intent after strict authorization and validation.
        Returns (handled, reply_text, embed).
        """
        category = intent["category"]
        action = intent["action"]
        guild = message.guild
        author = message.author
        is_unhinged = self._is_unhinged_active(guild.id if guild else None, author.id)

        # ---------------------------------------------------------------------
        # A. MUSIC EXECUTION
        # ---------------------------------------------------------------------
        if category == "music":
            if not guild:
                return True, "Music can only be played inside a server voice channel! 🌸", None

            music_mod = self.features.get("music")
            if not music_mod:
                return True, "Music module is not currently available.", None

            player = music_mod.get_player(guild)
            v_state = author.voice

            if action == "play":
                if not v_state or not v_state.channel:
                    msg = "You need to be in a voice channel first so I know where to join! 🎶" if not is_unhinged else "You're not even in a voice channel. Am I supposed to serenade the ghosts? 💀"
                    return True, msg, None

                # Join if not connected
                if not player.voice_client or not player.voice_client.is_connected():
                    bot_member = guild.me
                    can_connect, bot_err = self.permissions.check_bot_permissions(bot_member, None, ["connect", "speak"])
                    if not can_connect:
                        return True, f"❌ {bot_err}", None
                    await player.connect(v_state.channel)

                query = intent.get("query", "relaxing music")
                track = await player.play(query, message.channel)
                if track:
                    title = track.get("title", query)
                    reply = f"🎵 Now playing: **{title}**" if not is_unhinged else f"🔊 Dropping the beat: **{title}** (hope you have good taste) 💀"
                    return True, reply, None
                else:
                    return True, f"I couldn't find audio for '{query}'. 🌸", None

            elif action == "pause":
                if player.pause():
                    reply = "⏸️ Playback paused!" if not is_unhinged else "⏸️ Paused. Enjoy the quiet while it lasts 💀"
                    return True, reply, None
                return True, "Nothing is currently playing to pause! 🌸", None

            elif action == "resume":
                if player.resume():
                    reply = "▶️ Playback resumed!" if not is_unhinged else "▶️ Resumed! Back to the noise 🎶"
                    return True, reply, None
                return True, "Nothing is currently paused to resume! 🌸", None

            elif action == "skip":
                track = player.skip()
                if track:
                    reply = f"⏭️ Skipped! Next up: **{track.get('title', 'Next track')}**" if not is_unhinged else f"⏭️ Skipped! Next track loaded. Good riddance 💀"
                    return True, reply, None
                return True, "No more tracks in the queue to skip to! 🌸", None

            elif action == "stop":
                player.stop()
                reply = "⏹️ Playback stopped and queue cleared." if not is_unhinged else "⏹️ Stopped everything. Peace and quiet restored 🌸"
                return True, reply, None

            elif action == "queue":
                embed = player.get_queue_embed()
                return True, None, embed

            elif action == "nowplaying":
                embed = player.get_now_playing_embed()
                if embed:
                    return True, None, embed
                return True, "Nothing is currently playing! 🌸", None

            elif action == "shuffle":
                count = player.shuffle()
                if count > 1:
                    return True, f"🔀 Shuffled **{count}** tracks in the queue!", None
                return True, "Need at least 2 tracks in the queue to shuffle! 🌸", None

            elif action == "loop":
                mode = player.toggle_loop()
                status = "enabled 🔂" if mode else "disabled ➡️"
                return True, f"Loop mode has been **{status}**.", None

            elif action == "previous":
                track = await player.play_previous(message.channel)
                if track:
                    return True, f"⏪ Replaying: **{track.get('title', 'Previous track')}**", None
                return True, "No previous track history found! 🌸", None

            elif action == "disconnect":
                await player.disconnect()
                return True, "🚪 Left the voice channel. See you next time! 🌸", None

            elif action == "volume":
                vol = intent.get("volume", 100)
                player.set_volume(vol)
                return True, f"🔊 Volume set to **{vol}%**.", None

        # ---------------------------------------------------------------------
        # B. MODERATION EXECUTION
        # ---------------------------------------------------------------------
        elif category == "moderation":
            if not guild:
                return True, "Moderation actions can only be used inside a server! 🌸", None

            g_settings = self.db.get_guild_settings(str(guild.id)) if self.db else {}
            bot_member = guild.me

            # Check moderation permissions based on action
            req_perm = "manage_messages"
            if action in {"kick"}:
                req_perm = "kick_members"
            elif action in {"ban"}:
                req_perm = "ban_members"
            elif action in {"timeout", "untimeout", "warn"}:
                req_perm = "moderate_members"
            elif action in {"lock", "unlock", "slowmode"}:
                req_perm = "manage_channels"
            elif action in {"automod"}:
                req_perm = "manage_guild"

            is_auth, auth_err = self.permissions.check_permission(author, req_perm, g_settings)
            if not is_auth:
                denial = f"❌ {auth_err}" if not is_unhinged else f"❌ {auth_err} Who gave you the audacity to try that without permissions? 💀"
                return True, denial, None

            # User targeted actions
            if action in {"warn", "timeout", "untimeout", "kick", "ban"}:
                target, is_ambig = self._resolve_target_member(guild, intent.get("target_raw", ""), message)
                if is_ambig or not target:
                    return True, f"❓ I'm not sure which member you want to {action}. Please mention them clearly (e.g. `Kazumi, {action} @user`)! 🌸", None

                # Hierarchy check
                can_target, hier_err = self.permissions.check_hierarchy(author, target, bot_member)
                if not can_target:
                    return True, f"❌ {hier_err}", None

                reason = intent.get("reason", "Action requested via AI companion")

                if action == "warn":
                    case_id = self.db.create_case(guild.id, target.id, author.id, "WARN", reason)
                    warn_count = self.db.add_warning(str(guild.id), str(target.id), str(author.id), reason)
                    self.db.record_mod_action(str(guild.id), "WARN", str(target.id), str(author.id), reason)

                    embed = discord.Embed(
                        title=f"⚠️ Member Warned • Case #{case_id}",
                        description=f"**User:** {target.mention} (`{target.id}`)\n**Reason:** {reason}\n**Total Warnings:** {warn_count}",
                        color=0xf59e0b
                    )
                    return True, None, embed

                elif action == "timeout":
                    dur_str = intent.get("duration", "10m")
                    secs = parse_duration(dur_str)
                    if not secs or secs < 5:
                        return True, "❌ Please specify a valid duration (e.g. `5m`, `1h`, `1d`).", None

                    import datetime
                    until = discord.utils.utcnow() + datetime.timedelta(seconds=secs)
                    try:
                        await target.timeout(until, reason=f"Timeout by {author}: {reason}")
                        case_id = self.db.create_case(guild.id, target.id, author.id, "TIMEOUT", f"{reason} ({dur_str})")
                        self.db.record_mod_action(str(guild.id), "TIMEOUT", str(target.id), str(author.id), f"{reason} ({dur_str})")
                        embed = discord.Embed(
                            title=f"⏳ Member Timed Out • Case #{case_id}",
                            description=f"**User:** {target.mention}\n**Duration:** {dur_str}\n**Reason:** {reason}",
                            color=0xf59e0b
                        )
                        return True, None, embed
                    except Exception as e:
                        return True, f"❌ Failed to timeout {target.mention}: {e}", None

                elif action == "untimeout":
                    try:
                        await target.timeout(None, reason=f"Untimeout by {author}")
                        case_id = self.db.create_case(guild.id, target.id, author.id, "UNTIMEOUT", "Timeout removed")
                        self.db.record_mod_action(str(guild.id), "UNTIMEOUT", str(target.id), str(author.id), "Timeout removed")
                        return True, f"🕊️ Timeout removed for **{target.display_name}** (Case `#{case_id}`).", None
                    except Exception as e:
                        return True, f"❌ Failed to remove timeout: {e}", None

                elif action == "kick":
                    try:
                        await target.kick(reason=f"Kicked by {author}: {reason}")
                        case_id = self.db.create_case(guild.id, target.id, author.id, "KICK", reason)
                        self.db.record_mod_action(str(guild.id), "KICK", str(target.id), str(author.id), reason)
                        embed = discord.Embed(
                            title=f"👢 Member Kicked • Case #{case_id}",
                            description=f"**User:** {target.name} (`{target.id}`)\n**Reason:** {reason}\n**Moderator:** {author.mention}",
                            color=0xf43f5e
                        )
                        return True, None, embed
                    except Exception as e:
                        return True, f"❌ Failed to kick {target.name}: {e}", None

                elif action == "ban":
                    try:
                        await target.ban(reason=f"Banned by {author}: {reason}", delete_message_days=1)
                        case_id = self.db.create_case(guild.id, target.id, author.id, "BAN", reason)
                        self.db.record_mod_action(str(guild.id), "BAN", str(target.id), str(author.id), reason)
                        embed = discord.Embed(
                            title=f"🔨 Member Banned • Case #{case_id}",
                            description=f"**User:** {target.name} (`{target.id}`)\n**Reason:** {reason}\n**Moderator:** {author.mention}",
                            color=0xef4444
                        )
                        return True, None, embed
                    except Exception as e:
                        return True, f"❌ Failed to ban {target.name}: {e}", None

            # Channel level actions
            elif action == "lock":
                ch = message.channel
                try:
                    await ch.set_permissions(guild.default_role, send_messages=False)
                    case_id = self.db.create_case(guild.id, guild.default_role.id, author.id, "LOCK", f"Locked #{ch.name}")
                    self.db.record_mod_action(str(guild.id), "LOCK", str(ch.id), str(author.id), f"Locked #{ch.name}")
                    return True, f"🔒 **#{ch.name}** has been locked down! Members cannot send messages.", None
                except Exception as e:
                    return True, f"❌ Failed to lock channel: {e}", None

            elif action == "unlock":
                ch = message.channel
                try:
                    await ch.set_permissions(guild.default_role, send_messages=True)
                    case_id = self.db.create_case(guild.id, guild.default_role.id, author.id, "UNLOCK", f"Unlocked #{ch.name}")
                    self.db.record_mod_action(str(guild.id), "UNLOCK", str(ch.id), str(author.id), f"Unlocked #{ch.name}")
                    return True, f"🔓 **#{ch.name}** has been unlocked! Members can speak again.", None
                except Exception as e:
                    return True, f"❌ Failed to unlock channel: {e}", None

            elif action == "purge":
                amount = min(100, max(1, intent.get("amount", 10)))
                try:
                    deleted = await message.channel.purge(limit=amount + 1)
                    actual = max(0, len(deleted) - 1)
                    self.db.record_mod_action(str(guild.id), "PURGE", str(message.channel.id), str(author.id), f"Purged {actual} messages")
                    return True, f"🧹 Purged **{actual}** messages successfully!", None
                except Exception as e:
                    return True, f"❌ Failed to purge messages: {e}", None

            elif action == "slowmode":
                secs = intent.get("seconds", 0)
                try:
                    await message.channel.edit(slowmode_delay=secs)
                    msg = f"⏱️ Slowmode set to **{secs}s** in #{message.channel.name}." if secs > 0 else f"⏱️ Slowmode disabled in #{message.channel.name}."
                    return True, msg, None
                except Exception as e:
                    return True, f"❌ Failed to update slowmode: {e}", None

            elif action == "automod":
                enable = intent.get("enable", True)
                if not g_settings.get("automod"):
                    g_settings["automod"] = {}
                g_settings["automod"]["enabled"] = enable
                self.db.set_guild_settings(str(guild.id), g_settings)
                status = "enabled 🛡️" if enable else "disabled ⚠️"
                return True, f"AutoMod spam and content protection has been **{status}** for this server.", None

        # ---------------------------------------------------------------------
        # C. GIVEAWAY EXECUTION
        # ---------------------------------------------------------------------
        elif category == "giveaway":
            if not guild:
                return True, "Giveaways can only be hosted inside a Discord server! 🌸", None

            ga_mod = self.features.get("giveaways")
            if not ga_mod:
                return True, "Giveaway system is currently unavailable.", None

            is_auth, auth_err = self.permissions.check_permission(author, "manage_guild")
            if not is_auth:
                denial = f"❌ {auth_err}" if not is_unhinged else f"❌ {auth_err} Trying to give away stuff when you don't even manage the server? Nice try 💀"
                return True, denial, None

            if action == "create":
                dur_str = intent.get("duration", "24h")
                secs = parse_duration(dur_str)
                if not secs or secs < 10:
                    return True, "❌ Invalid duration. Please provide a duration like `10m`, `2h`, or `24h`.", None

                prize = intent.get("prize", "Mystery Prize 🎁")
                end_timestamp = time.time() + secs

                embed = discord.Embed(
                    title=f"🎉 GIVEAWAY: {prize}!",
                    description=(
                        f"Click **Enter Giveaway** below to participate!\n\n"
                        f"**Winners:** 1\n"
                        f"**Ends:** <t:{int(end_timestamp)}:R> (<t:{int(end_timestamp)}:f>)\n"
                        f"**Hosted by:** {author.mention}"
                    ),
                    color=0xf43f5e
                )
                embed.set_footer(text="Kazumi Giveaway System 🌸")

                from .giveaways import GiveawayEntryView
                view = GiveawayEntryView("pending")
                msg = await message.channel.send(embed=embed, view=view)

                ga_data = {
                    "message_id": str(msg.id),
                    "channel_id": str(message.channel.id),
                    "guild_id": str(guild.id),
                    "host_id": str(author.id),
                    "prize": prize,
                    "winners_count": 1,
                    "end_time": end_timestamp,
                    "required_role_id": None,
                    "min_account_days": 0,
                    "min_server_days": 0,
                    "entries": [],
                    "ended": False,
                    "paused": False,
                    "winners": []
                }
                self.db.set_giveaway(str(msg.id), ga_data)
                return True, f"🎉 Giveaway for **{prize}** created successfully in {message.channel.mention}!", None

            elif action == "list":
                active_gas = [g for g in self.db.get_guild_giveaways(str(guild.id)) if not g.get("ended")]
                if not active_gas:
                    return True, "There are currently no active giveaways running in this server! 🌸", None

                lines = []
                for g in active_gas:
                    entries = len(g.get("entries", []))
                    lines.append(f"• **{g.get('prize')}** (ID: `{g.get('message_id')}`) — **{entries}** entries, ends <t:{int(g.get('end_time', 0))}:R>")
                desc = "\n".join(lines)
                embed = discord.Embed(
                    title="🎉 Active Server Giveaways",
                    description=desc,
                    color=0xf43f5e
                )
                return True, None, embed

            elif action in {"end", "reroll"}:
                active_gas = [g for g in self.db.get_guild_giveaways(str(guild.id)) if (not g.get("ended") if action == "end" else g.get("ended"))]
                if not active_gas:
                    target_status = "active" if action == "end" else "concluded"
                    return True, f"No {target_status} giveaways found in this server! 🌸", None

                if len(active_gas) > 1:
                    return True, f"❓ Multiple giveaways found! Please use `/giveaway {action} message_id:<id>` to specify which giveaway! 🌸", None

                target_ga = active_gas[0]
                mid = target_ga["message_id"]

                if action == "end":
                    winners = await ga_mod.end_giveaway(mid)
                    if winners:
                        w_text = ", ".join(f"<@{w}>" for w in winners)
                        return True, f"🎉 Giveaway ended! Congratulations to {w_text} for winning **{target_ga.get('prize')}**!", None
                    return True, f"Giveaway ended for **{target_ga.get('prize')}**, but no eligible entries were found! 🌸", None

                elif action == "reroll":
                    new_w = await ga_mod.reroll_giveaway(mid)
                    if new_w:
                        w_text = ", ".join(f"<@{w}>" for w in new_w)
                        return True, f"🎲 Rerolled! Congratulations to the new winner(s): {w_text}!", None
                    return True, "No additional eligible entries found to reroll! 🌸", None

        return False, None, None
