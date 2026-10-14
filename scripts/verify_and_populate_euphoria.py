import asyncio
import os
import socket
import aiohttp
import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = 1546919406603337809

async def main():
    connector = aiohttp.TCPConnector(family=socket.AF_INET, ssl=True)
    intents = discord.Intents.default()
    intents.guilds = True
    intents.messages = True
    intents.message_content = True

    bot = commands.Bot(command_prefix="!", intents=intents, connector=connector)

    @bot.event
    async def on_ready():
        print(f"Logged in as {bot.user} (ID: {bot.user.id})")
        guild = bot.get_guild(GUILD_ID)
        if not guild:
            print(f"Guild {GUILD_ID} not found!")
            await bot.close()
            return

        print(f"=== GUILD: {guild.name} (ID: {guild.id}) ===")
        print(f"Features: {guild.features}")
        
        print("\n--- ROLES (Position descending) ---")
        for r in reversed(guild.roles):
            print(f"Pos {r.position}: '{r.name}' (ID: {r.id}, Managed: {r.managed}, Admin: {r.permissions.administrator})")

        print("\n--- CHANNELS ---")
        for cat in guild.categories:
            print(f"\n📁 Category: {cat.name} (ID: {cat.id})")
            for c in cat.channels:
                print(f"   - #{c.name} ({c.type}) (ID: {c.id})")

        uncat = [c for c in guild.channels if c.category is None and not isinstance(c, discord.CategoryChannel)]
        if uncat:
            print("\n📁 Uncategorized:")
            for c in uncat:
                print(f"   - #{c.name} ({c.type}) (ID: {c.id})")

        await bot.close()

    await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
