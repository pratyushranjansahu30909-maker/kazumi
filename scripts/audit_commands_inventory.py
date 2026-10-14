# -*- coding: utf-8 -*-
import os
import sys

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

import json
import asyncio
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
TARGET_GUILD_ID = 1554152397327044729

async def main():
    intents = discord.Intents.default()
    intents.members = True
    client = discord.Client(intents=intents)

    @client.event
    async def on_ready():
        try:
            guild = client.get_guild(TARGET_GUILD_ID)
            print(f"=== GUILD: {guild.name} ({guild.id}) ===")
            bots = [m for m in guild.members if m.bot]
            print(f"\nInstalled Bots in Gaman ({len(bots)}):")
            for b in bots:
                print(f" - {b.name}#{b.discriminator} (ID: {b.id})")

            # 1. Guild commands for Kazumi
            guild_cmds = await client.http.get_guild_commands(client.user.id, guild.id)
            print(f"\nGuild Commands for Kazumi on {guild.id}: {len(guild_cmds)}")
            for c in guild_cmds:
                print(f" - /{c['name']}: {c.get('description', '')}")

            # 2. Global commands for Kazumi
            global_cmds = await client.http.get_global_commands(client.user.id)
            print(f"\nGlobal Commands for Kazumi: {len(global_cmds)}")
            inventory = []
            for c in sorted(global_cmds, key=lambda x: x['name']):
                options = c.get('options', [])
                subcmds = []
                for opt in options:
                    if opt.get('type') == 1: # Subcommand
                        subcmds.append((opt['name'], opt.get('description', '')))
                    elif opt.get('type') == 2: # Subcommand group
                        group_name = opt['name']
                        for subopt in opt.get('options', []):
                            subcmds.append((f"{group_name} {subopt['name']}", subopt.get('description', '')))

                item = {
                    "id": c['id'],
                    "name": c['name'],
                    "description": c.get('description', ''),
                    "options": [o['name'] for o in options],
                    "subcommands": subcmds
                }
                inventory.append(item)
                if subcmds:
                    print(f" - /{c['name']} (Subcommands: {[s[0] for s in subcmds]}): {c.get('description', '')}")
                else:
                    print(f" - /{c['name']}: {c.get('description', '')}")

            with open("scripts/kazumi_registered_commands.json", "w", encoding="utf-8") as f:
                json.dump(inventory, f, indent=2, ensure_ascii=False)
            print(f"\nSaved {len(inventory)} registered commands to scripts/kazumi_registered_commands.json")

        except Exception as e:
            print(f"Error: {e}")
        finally:
            await client.close()

    await client.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
