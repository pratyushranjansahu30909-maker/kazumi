# -*- coding: utf-8 -*-
"""
KAZUMI ADVANCED FEATURE EXPANSION SUITE
Unified integration point for all modular systems:
- Database (Atomic JSON persistence in isa_memory)
- Moderation & AutoMod
- Server Event Logging
- Welcome & Goodbye Cards
- Auto-Role Management
- Interactive Ticket System
- Giveaways with Button Entries
- Reaction & Button Roles
- Custom Commands & Tag Dispatcher
- Server Info & Utility Tools
- Social Memory Graph & Server Memory
- Mood System & Smart Silence Engine
- Music System & Voice Controls
"""

import logging as std_logging
from typing import Dict, Any
import discord
from discord import app_commands
from discord.ext import commands

from .database import FeatureDatabase, get_feature_db, FeatureDB
from .moderation import AutoModTracker, register_moderation_commands
from .logging import ServerLogging, register_logging_commands
from .welcome import WelcomeSystem, register_welcome_commands
from .autorole import AutoRoleSystem, register_autorole_commands
from .tickets import (
    TicketManager,
    TicketLaunchView,
    TicketControlView,
    TicketClosedActionsView,
    register_ticket_commands
)
from .giveaways import GiveawayManager, GiveawayEntryView, register_giveaway_commands
from .reaction_roles import register_reaction_role_commands, DynamicRolePanelView
from .custom_commands import CustomCommandDispatcher, register_custom_command_slash
from .server_info import register_info_and_utility_commands
from .server_memory import (
    MoodManager,
    SocialGraphManager,
    ServerMemoryManager,
    ConversationContinuityTracker,
    SmartSilenceEngine,
    NaturalReactionPicker,
    KazumiMomentsEngine
)
from .music import setup_music_commands, MusicControlView

logger = std_logging.getLogger("KazumiFeatures")


def setup_all_features(bot: commands.Bot, tree: app_commands.CommandTree) -> Dict[str, Any]:
    """
    Registers all advanced commands into the Discord CommandTree
    and returns initialized manager instances.
    """
    logger.info("Initializing Kazumi Advanced Feature Suite...")
    db = get_feature_db()

    # 1. Moderation & AutoMod
    automod_tracker = AutoModTracker()
    register_moderation_commands(tree, bot)

    # 2. Server Logging
    server_logging = ServerLogging
    register_logging_commands(tree, bot)

    # 3. Welcome & Goodbye
    welcome_system = WelcomeSystem
    register_welcome_commands(tree, bot)

    # 4. AutoRole
    autorole_system = AutoRoleSystem
    register_autorole_commands(tree, bot)

    # 5. Tickets
    ticket_manager = TicketManager
    register_ticket_commands(tree, bot)

    # 6. Giveaways
    giveaway_manager = GiveawayManager
    register_giveaway_commands(tree, bot)

    # 7. Reaction / Button Roles
    register_reaction_role_commands(tree, bot)

    # 8. Custom Commands
    custom_command_dispatcher = CustomCommandDispatcher
    register_custom_command_slash(tree, bot)

    # 9. Server Info & Utilities
    register_info_and_utility_commands(tree, bot)

    # 10. Social Graph, Mood & Smart Silence
    mood_manager = MoodManager(db)
    social_graph = SocialGraphManager(db)
    server_memory = ServerMemoryManager(db)
    continuity_tracker = ConversationContinuityTracker()
    smart_silence = SmartSilenceEngine(bot.user.id if bot.user else 0)
    reaction_picker = NaturalReactionPicker()
    moments_engine = KazumiMomentsEngine(db)

    # 11. Music System
    setup_music_commands(tree, bot)

    # Register persistent views for button listeners across bot reboots
    try:
        bot.add_view(TicketLaunchView())
        bot.add_view(TicketControlView())
        bot.add_view(TicketClosedActionsView())
        bot.add_view(GiveawayEntryView())
    except Exception as e:
        logger.debug(f"Note on initial persistent view registration: {e}")

    logger.info("All Kazumi feature modules loaded and command handlers registered.")

    return {
        "db": db,
        "automod": automod_tracker,
        "logging": server_logging,
        "welcome": welcome_system,
        "autorole": autorole_system,
        "tickets": ticket_manager,
        "giveaways": giveaway_manager,
        "custom_commands": custom_command_dispatcher,
        "mood": mood_manager,
        "social_graph": social_graph,
        "server_memory": server_memory,
        "continuity": continuity_tracker,
        "smart_silence": smart_silence,
        "reaction_picker": reaction_picker,
        "moments": moments_engine
    }
