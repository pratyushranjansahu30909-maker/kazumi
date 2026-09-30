# 🌸 Kazumi Configuration Guide

Detailed reference for configuring Kazumi's modules, feature flags, permissions, and AI personality.

---

## 1. Environment Variables

| Variable | Type | Default | Description |
| :--- | :--- | :--- | :--- |
| `DISCORD_BOT_TOKEN` | string | `None` (Required) | Secret bot token for gateway connection. |
| `DISCORD_CHANNEL_ID` | integer | `None` | Dedicated channel ID for primary chatter. |
| `PREFIX` | string | `!k ` | Fallback prefix for text-based triggers. |
| `OPENAI_API_KEY` | string | `None` | Primary API key for LLM cognitive chat completions. |
| `PORT` | integer | `7860` | Express.js Web Dashboard HTTP listening port. |

---

## 2. Feature Flags (`discord_features/config.py`)

All feature modules can be dynamically enabled or disabled:

```python
FEATURE_FLAGS = {
    "moderation": True,
    "automod": True,
    "welcome": True,
    "autorole": True,
    "tickets": True,
    "giveaways": True,
    "music": True,
    "social_graph": True,
    "mood_engine": True,
    "smart_silence": True,
    "ambient_moments": True,
}
```

---

## 3. Server-Side Channel Modes

Channels can be classified into 3 operational modes via `/channelmode`:
- **`ACTIVE`**: Full chat replies, learning, reactions, and commands.
- **`OBSERVATION_ONLY`**: Silent learning, contextual reactions, zero conversational text messages.
- **`DISABLED`**: Completely ignored by Kazumi.
