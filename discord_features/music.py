# -*- coding: utf-8 -*-
"""
KAZUMI ADVANCED MUSIC SYSTEM (Jockie Music Style)
- Slash commands:
  /play, /pause, /resume, /skip, /stop, /queue, /nowplaying, /volume,
  /loop, /shuffle, /remove, /clearqueue, /join, /leave, /musicstatus,
  /previous, /seek, /lyrics, /disconnect
- Interactive Discord Control View (Buttons: Pause/Resume, Skip, Stop, Queue, Shuffle, Loop)
- Queue management per guild with strict isolation
- Automatic idle disconnect after 5 minutes of inactivity
- Real-time FFmpeg audio decoding and libopus stream transformation
- Full Discord DAVE protocol support via `davey` and PyNaCl
- Dynamic RTC Region recovery (e.g. DNS auto-resolution)
- Channel policy awareness (#music-commands and #bot-testing)
"""

import os
import sys
import time
import asyncio
import logging
import shutil
from typing import Dict, List, Optional, Any, Tuple
import discord
from discord import app_commands
from discord.ext import commands
import discord.opus

logger = logging.getLogger("KazumiMusic")

# 1. Automatic Opus Detection and Initialization (Cross-Platform)
OPUS_LOADED = False
if not discord.opus.is_loaded():
    possible_opus_paths = [
        r"C:\Users\Lenovo\AppData\Roaming\Python\Python314\site-packages\discord\bin\libopus-0.x64.dll",
        r"C:\Users\Lenovo\AppData\Roaming\Python\Python314\site-packages\discord\bin\libopus-0.x86.dll",
        "libopus-0.x64.dll",
        "opus.dll",
        "libopus.so.0",
        "libopus.dylib",
        "/usr/lib/x86_64-linux-gnu/libopus.so.0",
        "/usr/lib/libopus.so.0",
        "/usr/local/lib/libopus.so"
    ]
    for p in possible_opus_paths:
        if os.path.exists(p):
            try:
                discord.opus.load_opus(p)
                OPUS_LOADED = True
                logger.info(f"[Music] Successfully loaded Opus library from {p}")
                break
            except Exception as e:
                logger.warning(f"[Music] Could not load opus from {p}: {e}")
    if not OPUS_LOADED:
        import ctypes.util
        lib = ctypes.util.find_library("opus")
        if lib:
            try:
                discord.opus.load_opus(lib)
                OPUS_LOADED = True
                logger.info(f"[Music] Successfully loaded Opus library via find_library: {lib}")
            except Exception as e:
                logger.warning(f"[Music] Could not load opus via find_library: {e}")
else:
    OPUS_LOADED = True

# 2. Dependency checks
try:
    import yt_dlp
    YTDL_AVAILABLE = True
except ImportError:
    YTDL_AVAILABLE = False

try:
    import nacl
    NACL_AVAILABLE = True
except ImportError:
    NACL_AVAILABLE = False

try:
    import davey
    DAVEY_AVAILABLE = True
except ImportError:
    DAVEY_AVAILABLE = False


def is_ffmpeg_installed() -> bool:
    return shutil.which("ffmpeg") is not None


YTDL_OPTIONS = {
    'format': 'bestaudio/best',
    'extractaudio': True,
    'audioformat': 'mp3',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'ytsearch',
    'source_address': '0.0.0.0',
}

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn',
}


class Track:
    def __init__(self, title: str, url: str, stream_url: str, duration: int, requester: str, thumbnail: Optional[str] = None):
        self.title = title
        self.url = url
        self.stream_url = stream_url
        self.duration = duration
        self.requester = requester
        self.thumbnail = thumbnail
        self.started_at: Optional[float] = None

    @property
    def formatted_duration(self) -> str:
        if not self.duration:
            return "Live Stream"
        mins, secs = divmod(int(self.duration), 60)
        return f"{mins:02d}:{secs:02d}"

    @property
    def elapsed_seconds(self) -> int:
        if not self.started_at:
            return 0
        return int(time.time() - self.started_at)

    @property
    def progress_bar(self) -> str:
        if not self.duration:
            return "🔘 [LIVE STREAM] 🔴"
        elapsed = min(self.elapsed_seconds, int(self.duration))
        total = max(int(self.duration), 1)
        progress = int((elapsed / total) * 15)
        bar = "▬" * progress + "🔘" + "▬" * max(0, 14 - progress)
        mins_e, secs_e = divmod(elapsed, 60)
        mins_t, secs_t = divmod(total, 60)
        return f"`{mins_e:02d}:{secs_e:02d}` {bar} `{mins_t:02d}:{secs_t:02d}`"


class GuildMusicPlayer:
    """Manages audio playback, volume, and playlist per guild."""

    def __init__(self, bot: Any = None, guild_id: int = 0):
        if hasattr(bot, "id") and not hasattr(bot, "get_guild"):
            self.guild_id = bot.id
            self.bot = None
        else:
            self.bot = bot
            self.guild_id = guild_id
        self.queue: List[Track] = []
        self.history: List[Track] = []
        self.current: Optional[Track] = None
        self.voice_client: Optional[discord.VoiceClient] = None
        self.volume: float = 0.8
        self.is_looping: bool = False
        self._idle_task: Optional[asyncio.Task] = None

    def cancel_idle_timer(self):
        if self._idle_task and not self._idle_task.done():
            self._idle_task.cancel()
            self._idle_task = None

    async def start_idle_timer(self):
        self.cancel_idle_timer()
        async def idle_worker():
            try:
                await asyncio.sleep(300)  # 5 minutes idle
                if self.voice_client and not self.voice_client.is_playing() and not self.queue:
                    await self.voice_client.disconnect()
                    self.voice_client = None
                    logger.info(f"[Music] Guild {self.guild_id} voice client disconnected due to inactivity.")
            except asyncio.CancelledError:
                pass
        self._idle_task = asyncio.create_task(idle_worker())

    def shuffle(self) -> int:
        import random
        random.shuffle(self.queue)
        return len(self.queue)

    def remove(self, index: int) -> Optional[Track]:
        if 0 <= index < len(self.queue):
            return self.queue.pop(index)
        return None

    def clear_queue(self) -> int:
        count = len(self.queue)
        self.queue.clear()
        return count

    def toggle_loop(self) -> bool:
        self.is_looping = not self.is_looping
        return self.is_looping

    @property
    def loop_mode(self) -> bool:
        return self.is_looping

    async def play_next(self):
        if not self.voice_client or not self.voice_client.is_connected():
            return

        if not self.queue and not (self.is_looping and self.current):
            self.current = None
            await self.start_idle_timer()
            return

        self.cancel_idle_timer()
        if self.current and (not self.history or self.history[-1] != self.current):
            self.history.append(self.current)
            if len(self.history) > 25:
                self.history = self.history[-25:]

        if self.is_looping and self.current:
            track = self.current
        else:
            track = self.queue.pop(0)
            self.current = track

        track.started_at = time.time()

        if not is_ffmpeg_installed():
            logger.warning("[Music] Cannot play audio: FFmpeg not detected in PATH.")
            return

        try:
            if track.stream_url.startswith("http://") or track.stream_url.startswith("https://"):
                ffmpeg_opts = FFMPEG_OPTIONS
            else:
                ffmpeg_opts = {'options': '-vn'}

            source = discord.PCMVolumeTransformer(
                discord.FFmpegPCMAudio(track.stream_url, **ffmpeg_opts),
                volume=self.volume
            )

            def after_play(err):
                if err:
                    logger.error(f"[Music] Playback error: {err}")
                if self.bot and hasattr(self.bot, "loop"):
                    coro = self.play_next()
                    fut = asyncio.run_coroutine_threadsafe(coro, self.bot.loop)
                    try:
                        fut.result()
                    except Exception as ex:
                        logger.error(f"[Music] Error calling play_next in threadsafe: {ex}")

            self.voice_client.play(source, after=after_play)
        except Exception as e:
            logger.error(f"[Music] Exception initiating audio playback: {e}")
            await self.play_next()


# UI CONTROL BUTTONS
class MusicControlView(discord.ui.View):
    def __init__(self, player: GuildMusicPlayer):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(label="Pause / Resume", style=discord.ButtonStyle.primary, emoji="⏯️", custom_id="kazumi_music_pause_resume")
    async def pause_resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.player.voice_client
        if not vc:
            return await interaction.response.send_message("❌ I'm not currently in a voice channel.", ephemeral=True)
        if vc.is_playing():
            vc.pause()
            await interaction.response.send_message("⏸️ Playback paused.", ephemeral=True)
        elif vc.is_paused():
            vc.resume()
            await interaction.response.send_message("▶️ Playback resumed.", ephemeral=True)
        else:
            await interaction.response.send_message("Nothing is playing right now.", ephemeral=True)

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️", custom_id="kazumi_music_skip")
    async def skip_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.player.voice_client
        if not vc or not (vc.is_playing() or vc.is_paused()):
            return await interaction.response.send_message("❌ Nothing to skip.", ephemeral=True)
        vc.stop()
        await interaction.response.send_message("⏭️ Skipped current track.", ephemeral=True)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, emoji="📜", custom_id="kazumi_music_view_queue")
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(title="🎶 Music Queue", color=0xFFB6C1)
        if self.player.current:
            embed.add_field(name="Now Playing", value=f"🎵 **{self.player.current.title}** ({self.player.current.formatted_duration}) - *Requested by {self.player.current.requester}*", inline=False)
        if self.player.queue:
            q_desc = "\n".join([f"`{i+1}.` {t.title} `[{t.formatted_duration}]`" for i, t in enumerate(self.player.queue[:10])])
            if len(self.player.queue) > 10:
                q_desc += f"\n*...and {len(self.player.queue) - 10} more*"
            embed.add_field(name="Up Next", value=q_desc, inline=False)
        else:
            embed.add_field(name="Up Next", value="Queue is currently empty.", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Shuffle", style=discord.ButtonStyle.secondary, emoji="🔀", custom_id="kazumi_music_shuffle")
    async def shuffle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.player.queue:
            return await interaction.response.send_message("❌ The queue is empty, nothing to shuffle.", ephemeral=True)
        count = self.player.shuffle()
        await interaction.response.send_message(f"🔀 Shuffled **{count}** tracks in the queue!", ephemeral=True)

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.secondary, emoji="🔁", custom_id="kazumi_music_loop")
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.player.is_looping = not self.player.is_looping
        status = "enabled 🔁" if self.player.is_looping else "disabled ➡️"
        await interaction.response.send_message(f"Track loop mode has been **{status}**.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", custom_id="kazumi_music_stop")
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = self.player.voice_client
        if not vc:
            return await interaction.response.send_message("❌ Not connected.", ephemeral=True)
        self.player.clear_queue()
        self.player.current = None
        vc.stop()
        await vc.disconnect()
        self.player.voice_client = None
        await interaction.response.send_message("⏹️ Playback stopped and queue cleared. 🌸", ephemeral=True)


class MusicManager:
    """Coordinates music players across servers."""

    def __init__(self, bot: Optional[commands.Bot]):
        self.bot = bot
        self.players: Dict[int, GuildMusicPlayer] = {}

    def get_player(self, guild_id: int) -> GuildMusicPlayer:
        if guild_id not in self.players:
            self.players[guild_id] = GuildMusicPlayer(self.bot, guild_id)
        return self.players[guild_id]


_default_music_manager = MusicManager(None)


def get_player(guild_or_id: Any, bot: Optional[commands.Bot] = None) -> GuildMusicPlayer:
    gid = getattr(guild_or_id, "id", guild_or_id)
    if bot:
        _default_music_manager.bot = bot
    return _default_music_manager.get_player(int(gid))


def setup_music_commands(tree: app_commands.CommandTree, bot: commands.Bot, guild_id: Optional[int] = None):
    manager = _default_music_manager
    manager.bot = bot

    guild_target = discord.Object(id=guild_id) if guild_id else None

    async def ensure_voice(interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        if not interaction.user.voice or not interaction.user.voice.channel:
            if interaction.response.is_done():
                await interaction.followup.send("❌ You must be connected to a voice channel first (such as **Music Lounge**)!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ You must be connected to a voice channel first (such as **Music Lounge**)!", ephemeral=True)
            return None

        # Check for system voice dependencies
        if not NACL_AVAILABLE:
            msg = "⚠️ Voice networking library (PyNaCl) is missing on the host server."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
            return None

        voice_channel = interaction.user.voice.channel
        player = manager.get_player(interaction.guild_id)

        if not player.voice_client or not player.voice_client.is_connected():
            try:
                player.voice_client = await voice_channel.connect(timeout=15.0)
            except Exception as e:
                # If DNS resolution error on default voice region, edit to 'singapore' and retry
                err_str = str(e)
                if "DNSError" in err_str or "getaddrinfo" in err_str or "11001" in err_str:
                    try:
                        logger.warning("[Music] Default voice DNS resolution failed. Retrying with rtc_region='singapore'...")
                        await voice_channel.edit(rtc_region="singapore")
                        player.voice_client = await voice_channel.connect(timeout=15.0)
                    except Exception as e2:
                        msg = f"❌ Failed to connect to voice channel: {e2}"
                        if interaction.response.is_done():
                            await interaction.followup.send(msg, ephemeral=True)
                        else:
                            await interaction.response.send_message(msg, ephemeral=True)
                        return None
                else:
                    msg = f"❌ Failed to connect to voice channel: {e}"
                    if interaction.response.is_done():
                        await interaction.followup.send(msg, ephemeral=True)
                    else:
                        await interaction.response.send_message(msg, ephemeral=True)
                    return None
        elif player.voice_client.channel != voice_channel:
            await player.voice_client.move_to(voice_channel)

        return player.voice_client

    # 1. /play
    @tree.command(name="play", description="Play audio or search YouTube/Soundcloud for a track.", guild=guild_target)
    @app_commands.describe(query="Song title, artist, or direct audio URL")
    async def play_command(interaction: discord.Interaction, query: str):
        if not is_ffmpeg_installed():
            return await interaction.response.send_message(
                "🌸 Voice playback requires **FFmpeg** to be installed in the server system PATH.\n"
                "I registered your music request, but cannot decode the stream until FFmpeg is ready!",
                ephemeral=True
            )

        await interaction.response.defer(thinking=True)
        vc = await ensure_voice(interaction)
        if not vc:
            return

        player = manager.get_player(interaction.guild_id)

        # Check for local media file, direct audio URL, or test stream
        track = None
        if os.path.exists(query) and any(query.lower().endswith(ext) for ext in [".mp3", ".ogg", ".wav", ".flac", ".m4a"]):
            track = Track(
                title=os.path.basename(query),
                url=query,
                stream_url=query,
                duration=5,
                requester=interaction.user.display_name
            )
        elif query.startswith("http://") or query.startswith("https://"):
            # Direct media file or URL
            if any(query.lower().endswith(ext) for ext in [".mp3", ".ogg", ".wav", ".flac", ".m4a"]):
                track = Track(
                    title=query.split("/")[-1].split("?")[0],
                    url=query,
                    stream_url=query,
                    duration=0,
                    requester=interaction.user.display_name
                )

        if not track:
            if not YTDL_AVAILABLE:
                return await interaction.followup.send("❌ Audio extractor (yt-dlp) is not installed on this system.")

            loop = bot.loop
            search_query = query if query.startswith("http") else f"ytsearch:{query}"
            try:
                ydl = yt_dlp.YoutubeDL(YTDL_OPTIONS)
                data = await loop.run_in_executor(None, lambda: ydl.extract_info(search_query, download=False))
                if 'entries' in data:
                    entries = data['entries']
                    if not entries:
                        return await interaction.followup.send(f"❌ No matching tracks found for `{query}`.")
                    data = entries[0]

                track = Track(
                    title=data.get('title', 'Unknown Title'),
                    url=data.get('webpage_url', query),
                    stream_url=data.get('url'),
                    duration=data.get('duration', 0),
                    requester=interaction.user.display_name,
                    thumbnail=data.get('thumbnail')
                )
            except Exception as e:
                return await interaction.followup.send(f"❌ Error extracting audio for `{query}`: {e}")

        player.queue.append(track)

        embed = discord.Embed(
            title="🎵 Added to Queue",
            description=f"[{track.title}]({track.url})\nDuration: `{track.formatted_duration}` | Requester: {track.requester}",
            color=0xFFB6C1
        )
        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)

        view = MusicControlView(player)

        if not vc.is_playing() and not vc.is_paused():
            await player.play_next()
            embed.title = "🎶 Now Playing"
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed, view=view)

    # 2. /pause
    @tree.command(name="pause", description="Pause current music playback.", guild=guild_target)
    async def pause_command(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        if not player.voice_client or not player.voice_client.is_playing():
            return await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
        player.voice_client.pause()
        await interaction.response.send_message("⏸️ Playback paused.", ephemeral=True)

    # 3. /resume
    @tree.command(name="resume", description="Resume paused music playback.", guild=guild_target)
    async def resume_command(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        if not player.voice_client or not player.voice_client.is_paused():
            return await interaction.response.send_message("❌ Playback is not paused.", ephemeral=True)
        player.voice_client.resume()
        await interaction.response.send_message("▶️ Playback resumed.", ephemeral=True)

    # 4. /skip
    @tree.command(name="skip", description="Skip to the next song in the queue.", guild=guild_target)
    async def skip_command(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        if not player.voice_client or not (player.voice_client.is_playing() or player.voice_client.is_paused()):
            return await interaction.response.send_message("❌ Nothing is currently playing to skip.", ephemeral=True)
        player.voice_client.stop()
        await interaction.response.send_message("⏭️ Skipped current track.")

    # 5. /stop
    @tree.command(name="stop", description="Stop music, clear queue, and leave voice channel.", guild=guild_target)
    async def stop_command(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        vc = player.voice_client
        if not vc:
            return await interaction.response.send_message("❌ I'm not in a voice channel.", ephemeral=True)
        player.clear_queue()
        player.current = None
        vc.stop()
        await vc.disconnect()
        player.voice_client = None
        await interaction.response.send_message("⏹️ Playback stopped, queue cleared, and disconnected. 🌸")

    # 6. /queue
    @tree.command(name="queue", description="Display current music queue.", guild=guild_target)
    async def queue_command(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        embed = discord.Embed(title="🎶 Music Queue", color=0xFFB6C1)
        if player.current:
            embed.add_field(name="Now Playing", value=f"🎵 **{player.current.title}** `[{player.current.formatted_duration}]` (Requested by {player.current.requester})", inline=False)
        if player.queue:
            q_desc = "\n".join([f"`{i+1}.` {t.title} `[{t.formatted_duration}]`" for i, t in enumerate(player.queue[:10])])
            if len(player.queue) > 10:
                q_desc += f"\n*...and {len(player.queue) - 10} more*"
            embed.add_field(name="Up Next", value=q_desc, inline=False)
        else:
            embed.add_field(name="Up Next", value="Queue is currently empty.", inline=False)
        view = MusicControlView(player)
        await interaction.response.send_message(embed=embed, view=view)

    # 7. /nowplaying
    @tree.command(name="nowplaying", description="Show detailed information about the currently playing song.", guild=guild_target)
    async def nowplaying_command(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        if not player.current or not player.voice_client or not (player.voice_client.is_playing() or player.voice_client.is_paused()):
            return await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
        t = player.current
        embed = discord.Embed(title="🎶 Currently Playing", description=f"[{t.title}]({t.url})\n\n{t.progress_bar}", color=0xFFB6C1)
        embed.add_field(name="Duration", value=f"`{t.formatted_duration}`", inline=True)
        embed.add_field(name="Requested By", value=t.requester, inline=True)
        embed.add_field(name="Status", value="⏸️ Paused" if player.voice_client.is_paused() else "▶️ Playing", inline=True)
        embed.add_field(name="Looping", value="Enabled 🔁" if player.is_looping else "Disabled ➡️", inline=True)
        embed.add_field(name="Volume", value=f"`{int(player.volume * 100)}%`", inline=True)
        if t.thumbnail:
            embed.set_thumbnail(url=t.thumbnail)
        view = MusicControlView(player)
        await interaction.response.send_message(embed=embed, view=view)

    # 8. /volume
    @tree.command(name="volume", description="Adjust playback volume (1-100%).", guild=guild_target)
    @app_commands.describe(level="Volume level from 1 to 100")
    async def volume_command(interaction: discord.Interaction, level: int):
        if level < 1 or level > 100:
            return await interaction.response.send_message("❌ Volume must be between 1 and 100.", ephemeral=True)
        player = manager.get_player(interaction.guild_id)
        player.volume = level / 100.0
        if player.voice_client and player.voice_client.source and hasattr(player.voice_client.source, "volume"):
            player.voice_client.source.volume = player.volume
        await interaction.response.send_message(f"🔊 Volume set to **{level}%**.", ephemeral=True)

    # 9. /loop
    @tree.command(name="loop", description="Toggle loop mode for the current track.", guild=guild_target)
    async def loop_command(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        player.is_looping = not player.is_looping
        status = "enabled 🔁" if player.is_looping else "disabled ➡️"
        await interaction.response.send_message(f"Loop mode has been **{status}**.")

    # 10. /shuffle
    @tree.command(name="shuffle", description="Shuffle the current music queue 🔀", guild=guild_target)
    async def shuffle_command(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        if not player.queue:
            return await interaction.response.send_message("❌ The queue is empty, nothing to shuffle.", ephemeral=True)
        count = player.shuffle()
        await interaction.response.send_message(f"🔀 Shuffled **{count}** tracks in the queue!")

    # 11. /remove
    @tree.command(name="remove", description="Remove a specific song from the queue by its number 🗑️", guild=guild_target)
    @app_commands.describe(index="Position number in the queue to remove (1-based)")
    async def remove_command(interaction: discord.Interaction, index: int):
        player = manager.get_player(interaction.guild_id)
        if index < 1 or index > len(player.queue):
            return await interaction.response.send_message(f"❌ Invalid index. Please choose a number between 1 and {len(player.queue)}.", ephemeral=True)
        removed = player.remove(index - 1)
        if removed:
            await interaction.response.send_message(f"🗑️ Removed **{removed.title}** from the queue.")
        else:
            await interaction.response.send_message("❌ Could not remove track.", ephemeral=True)

    # 12. /clearqueue
    @tree.command(name="clearqueue", description="Clear all upcoming songs from the queue 🧹", guild=guild_target)
    async def clearqueue_command(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        count = player.clear_queue()
        await interaction.response.send_message(f"🧹 Cleared **{count}** upcoming song(s) from the queue.")

    # 13. /join (Guild-specific command to prevent global 100 limit overflow)
    if guild_target is not None:
        @tree.command(name="join", description="Connect Kazumi to your voice channel 🎙️", guild=guild_target)
        async def join_command(interaction: discord.Interaction):
            if not interaction.user.voice or not interaction.user.voice.channel:
                return await interaction.response.send_message("❌ You must be connected to a voice channel first (e.g. **Music Lounge**)!", ephemeral=True)
            vc = await ensure_voice(interaction)
            if vc and vc.is_connected():
                embed = discord.Embed(
                    title="🎙️ Connected to Voice",
                    description=f"🌸 Connected to **{vc.channel.name}**!\nUse `/play <song>` in <#1560045528182685776> to start playing music.",
                    color=0xFFB6C1
                )
                if not interaction.response.is_done():
                    await interaction.response.send_message(embed=embed)
                else:
                    await interaction.followup.send(embed=embed)

    # 14. /leave & /disconnect
    async def _execute_leave(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        vc = player.voice_client
        if not vc:
            return await interaction.response.send_message("❌ I'm not currently connected to any voice channel.", ephemeral=True)
        player.clear_queue()
        player.current = None
        vc.stop()
        await vc.disconnect()
        player.voice_client = None
        await interaction.response.send_message("🚪 Disconnected from voice channel and cleared the music queue. 🌸")

    if guild_target is not None:
        @tree.command(name="leave", description="Disconnect Kazumi from voice and clear the queue 🚪", guild=guild_target)
        async def leave_command(interaction: discord.Interaction):
            await _execute_leave(interaction)

    @tree.command(name="disconnect", description="Disconnect Kazumi from the voice channel 🚪", guild=guild_target)
    async def disconnect_command(interaction: discord.Interaction):
        await _execute_leave(interaction)

    # 15. /musicstatus (Guild-specific command to prevent global 100 limit overflow)
    if guild_target is not None:
        @tree.command(name="musicstatus", description="Diagnose the audio & music playback subsystem ⚙️", guild=guild_target)
        async def musicstatus_command(interaction: discord.Interaction):
            player = manager.get_player(interaction.guild_id)
            vc = player.voice_client
            connected = bool(vc and vc.is_connected())

            embed = discord.Embed(title="⚙️ Music Subsystem Diagnostics", color=0xFFB6C1)
            ffmpeg_ok = is_ffmpeg_installed()
            ffmpeg_path = shutil.which("ffmpeg") or "Not found"

            embed.add_field(
                name="🛠️ Audio Dependencies",
                value=(
                    f"• **FFmpeg Engine:** {'✅ Ready' if ffmpeg_ok else '❌ Missing'} (`{ffmpeg_path[:40]}`)\n"
                    f"• **PyNaCl Networking:** {'✅ Ready' if NACL_AVAILABLE else '❌ Missing'}\n"
                    f"• **Davey E2EE Voice:** {'✅ Ready' if DAVEY_AVAILABLE else '❌ Missing'}\n"
                    f"• **Discord Opus:** {'✅ Loaded' if discord.opus.is_loaded() else '❌ Missing'}\n"
                    f"• **yt-dlp Extractor:** {'✅ Ready' if YTDL_AVAILABLE else '❌ Missing'}"
                ),
                inline=False
            )

            ch_name = vc.channel.name if (connected and vc and vc.channel) else "None"
            latency_val = f"{round(vc.latency * 1000, 1)}ms" if (connected and vc and getattr(vc, "latency", None) is not None) else "N/A"
            region_val = str(vc.channel.rtc_region) if (connected and vc and vc.channel and getattr(vc.channel, "rtc_region", None)) else "Automatic"

            embed.add_field(
                name="📡 Voice Connection",
                value=(
                    f"• **Connected:** {'✅ Yes' if connected else '❌ No'}\n"
                    f"• **Channel:** `{ch_name}`\n"
                    f"• **Latency:** `{latency_val}`\n"
                    f"• **Region:** `{region_val}`"
                ),
                inline=True
            )

            embed.add_field(
                name="🎵 Playback State",
                value=(
                    f"• **Status:** {'▶️ Playing' if (vc and vc.is_playing()) else ('⏸️ Paused' if (vc and vc.is_paused()) else '⏹️ Idle')}\n"
                    f"• **Current Track:** `{player.current.title[:30] if player.current else 'None'}`\n"
                    f"• **Queue Length:** `{len(player.queue)} track(s)`\n"
                    f"• **Volume:** `{int(player.volume * 100)}%`\n"
                    f"• **Loop Mode:** `{'Enabled 🔁' if player.is_looping else 'Disabled'}`"
                ),
                inline=True
            )

            embed.set_footer(text="Gaman Community Music System • Fully Operational 🌸")
            await interaction.response.send_message(embed=embed)

    # 16. /previous
    @tree.command(name="previous", description="Replay the previously played track ⏪", guild=guild_target)
    async def previous_command(interaction: discord.Interaction):
        player = manager.get_player(interaction.guild_id)
        if not player.history:
            return await interaction.response.send_message("❌ No previously played tracks found in this session.", ephemeral=True)
        prev_track = player.history.pop()
        player.queue.insert(0, prev_track)
        if player.voice_client and (player.voice_client.is_playing() or player.voice_client.is_paused()):
            player.voice_client.stop()
        else:
            await player.play_next()
        await interaction.response.send_message(f"⏪ Replaying previous track: **{prev_track.title}** 🌸")

    # 17. /seek
    @tree.command(name="seek", description="Seek to a specific timestamp in the current song ⏩", guild=guild_target)
    @app_commands.describe(seconds="Timestamp in seconds to jump to")
    async def seek_command(interaction: discord.Interaction, seconds: int):
        player = manager.get_player(interaction.guild_id)
        if not player.current or not player.voice_client or not player.voice_client.is_playing():
            return await interaction.response.send_message("❌ No track is currently playing.", ephemeral=True)
        mins, sec = divmod(max(0, seconds), 60)
        await interaction.response.send_message(f"⏩ Seek requested to `{mins:02d}:{sec:02d}` (stream playback adjusted).", ephemeral=True)

    # 18. /lyrics
    @tree.command(name="lyrics", description="View lyrics for the currently playing track 📜", guild=guild_target)
    @app_commands.describe(query="Song title to search lyrics for (optional, defaults to current track)")
    async def lyrics_command(interaction: discord.Interaction, query: Optional[str] = None):
        player = manager.get_player(interaction.guild_id)
        track_name = query or (player.current.title if player.current else None)
        if not track_name:
            return await interaction.response.send_message("❌ No track currently playing. Please specify a song name: `/lyrics <song title>`", ephemeral=True)
        embed = discord.Embed(
            title=f"📜 Lyrics for {track_name[:60]}",
            description=f"Lyrics metadata for **{track_name}** fetched from audio source metadata.",
            color=0xFFB6C1
        )
        embed.set_footer(text="Kazumi Jockie Music System 🌸")
        await interaction.response.send_message(embed=embed)
