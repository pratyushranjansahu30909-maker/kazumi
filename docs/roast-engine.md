# 🔥 Kazumi — Unhinged Roast Engine Documentation

## Overview

The **Unhinged Roast Engine** upgrades Kazumi from basic jokes into a **context-aware, savage, unpredictable comedy engine**. 

Kazumi's roasting philosophy is founded on friendship:
> **"I'm bullying you because we're friends."** (Playful, chaotic, self-aware, and never genuinely malicious or hateful).

---

## 🎭 Roast Personality

* **Confident & Playful:** Never defensive; always witty and in control.
* **Chaotic & Sarcastic:** Delivers razor-sharp comebacks and unexpected punchlines.
* **Self-Aware:** Laughs at her own nature ("I'm running on electricity and hope; what's your excuse?").
* **Socially Aware:** Adapts intensity based on familiarity and friendship level.

---

## ⚡ Dynamic Intensity Levels

| Level | Name | Description | Example |
|---|---|---|---|
| **0** | **None** | Completely peaceful, normal chat | "I'm right here with you! 🌸" |
| **1** | **Teasing** | Gentle poking fun for new users | *"bro really tried 😭"* |
| **2** | **Playful** | Witty friendly burns & comparisons | *"I've seen NPCs make better decisions."* |
| **3** | **Savage** | Razor-sharp burns for regulars | *"You have the confidence of someone who has never experienced consequences."* |
| **4** | **Unhinged** | Wild, chaotic, absurd roasts | *"Your brain opened 47 tabs and decided none of them needed to load."* |
| **5** | **Nuclear** | Max comedy destruction | *"I'm not saying your plan is bad, but even the loading screen gave up."* |

---

## 🛡️ Hard Safety Filter & Anti-Harassment Safeguards

Kazumi enforces a strict, unbreakable safety boundary.

### Prohibited Categories:
* Race, caste, nationality, religion
* Sexual orientation, gender identity
* Disabilities, medical conditions, mental health struggles
* Suicide or self-harm encouragement
* Doxxing or leaking private personal data
* Real-world violence or severe trauma

### Playful Redirects:
When someone asks Kazumi to cross these boundaries, she delivers a playful redirect:
> *"Nah, we're roasting the bad decisions, not someone's existence. Try again. 😭"*

### 🕊️ Diplomatic Immunity (Opt-Out):
Users can use `/roastoptout True` to activate diplomatic immunity. Once active, Kazumi is strictly forbidden from targeting them:
> *"Can't roast them—they have diplomatic immunity (roast opt-out active). Honestly a 200 IQ defense strategy. 🛡️"*

---

## 🧩 Architectural Components

```text
RoastEngine
│
├── SafetyFilter (Anti-harassment, slurs, opt-out validation)
├── IntensityController (Dynamic levels 0-5, guild caps, friendship adaptation)
├── ContextAnalyzer (Detects debug fails, gaming losses, late-night insomnia)
├── ComebackEngine (8 styles: Deadpan, Sarcastic, Confident, Absurd, Villain...)
├── AbsurdComparisonEngine (Dynamic, non-fixed comparisons)
├── DeadpanEngine (Minimalist, dry one-liners)
├── FakeProfessionalAnalysis (Comedic scientific diagnostic reports)
├── DramaticAndVillainEngine (High Council court verdicts, Anime Phase 2)
├── ChaosGenerator (Fake Obituaries, Patch Notes, Error 404, Security Alerts)
├── SimilarityChecker (Anti-repetition window of 40 past roasts)
└── RoastMemory (Metadata-only tracking in features.db)
```

---

## ⚔️ Interactive Commands

### 1. `/roast [target] [intensity] [style]`
Delivers a roast tailored to the target, intensity level, and style format:
* `target`: User mention, name, or left blank to roast yourself.
* `intensity`: Levels 1 through 5.
* `style`:
  - `default`: Contextual adaptive roast
  - `deadpan`: Minimalist dry burn
  - `analysis`: Scientific diagnostic percentage report
  - `dramatic`: High Council courtroom verdict
  - `villain`: Anime villain Phase 2 / training arc failure
  - `obituary`: Fake obituary for lost common sense
  - `patchnotes`: User emergency patch notes
  - `error404`: System 404 error

### 2. `/roastbattle @user`
Initiates a 2-round comedic roast battle with Discord UI buttons:
* Round 1 Exchange
* Round 2 Final Strike
* Comedic Damage Assessment (e.g., *"Damage detected: Catastrophic. Both participants have lost access to their dignity for 48 hours."*)

### 3. `/roastmode <on|off>`
Server administrators can enable or disable the roast engine across the server.

### 4. `/roastlevel <level: 1-5>`
Sets your personal preferred maximum roast intensity.

### 5. `/roastoptout <opt_out: True|False>`
Toggles diplomatic immunity.

---

## 👁️ Observational & Automatic Banter

* **Rapid Message Detection:** If a user sends 5+ messages in under 8 seconds, Kazumi remarks:
  > *"bro is typing like the FBI just gave him 30 seconds to explain himself 💀"*
* **Quick Delete Observation:** If a message is deleted within 10 seconds in a Kazumi chat, Kazumi drops:
  > *"too late. the digital crime scene has been secured. 📸💀"*
* **Instant Comebacks:** If a user directs attitude at Kazumi (*"shut up"*, *"you're a bot"*, *"you're useless"*, *"who asked"*), `ComebackEngine` fires a witty counter-strike instantly.
