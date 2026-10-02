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

from .config import KazumiConfig, sanitize_secrets, SanitizedLogFormatter
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
from .roast_engine import (
    RoastEngine,
    IntensityLevel,
    IntensityController,
    SafetyFilter,
    ComebackEngine,
    ContextAnalyzer,
    AbsurdComparisonEngine,
    DeadpanEngine,
    FakeProfessionalAnalysis,
    DramaticAndVillainEngine,
    ChaosGenerator,
    SimilarityChecker,
    RoastBattleView,
    register_roast_commands
)
from .case_system import CaseManager, ReportManager, AppealManager, register_case_commands
from .security import AntiRaidEngine, AntiNukeEngine, StaffPermissionManager, register_security_commands
from .game_engine import GameEngine, get_game_engine, register_game_commands
from .human_interaction import HumanInteractionEngine, InteractionDecision

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

    # 12. Unhinged Roast Engine (Sections 1-28)
    roast_engine = RoastEngine(db)
    register_roast_commands(tree, bot, roast_engine, db)

    # 13. Moderation Case Management, Reports & Appeals
    case_manager = CaseManager(db)
    register_case_commands(tree, bot, db)

    # 14. Server Security, Anti-Raid & Anti-Nuke
    anti_raid_engine = AntiRaidEngine(db)
    anti_nuke_engine = AntiNukeEngine(db)
    register_security_commands(tree, bot, db)

    # 15. Game Engine & Arcade Suite
    game_engine = get_game_engine(db)
    register_game_commands(tree, bot, db)

    # 16. Human Interaction Engine (Social decision layer)
    human_interaction = HumanInteractionEngine(db, bot.user.id if bot.user else 0)

    # Register persistent views for button listeners across bot reboots
    try:
        bot.add_view(TicketLaunchView())
        bot.add_view(TicketControlView())
        bot.add_view(TicketClosedActionsView())
        bot.add_view(GiveawayEntryView())
    except Exception as e:
        logger.debug(f"Note on initial persistent view registration: {e}")

    from . import music
    from .permissions import PermissionService
    from .intent_router import NaturalIntentRouter
    from .announcements import setup_announcement_commands
    from .stage import setup_stage_commands

    announcement_scheduler = setup_announcement_commands(tree, bot, db)
    setup_stage_commands(tree, bot, db)

    intent_router = NaturalIntentRouter(bot, {
        "db": db,
        "automod": automod_tracker,
        "logging": server_logging,
        "giveaways": giveaway_manager,
        "music": music,
        "roast_engine": roast_engine,
        "case_manager": case_manager
    })

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
        "moments": moments_engine,
        "roast_engine": roast_engine,
        "case_manager": case_manager,
        "anti_raid": anti_raid_engine,
        "anti_nuke": anti_nuke_engine,
        "game_engine": game_engine,
        "human_interaction": human_interaction,
        "music": music,
        "permissions": PermissionService,
        "intent_router": intent_router
    }
