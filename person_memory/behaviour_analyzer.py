"""
🌸 Kazumi Person Memory — Behaviour Analyzer
Fast, lightweight, rule-based & heuristic analysis of user communication.
Runs entirely locally with zero heavy LLM latency or cost per message.
Adheres strictly to privacy, safety, and anti-creepy constraints.
"""

import re
import unicodedata
from typing import Dict, List, Any, Optional, Set, Tuple

# Safe general interests / hobbies whitelist for topic extraction
SAFE_INTEREST_KEYWORDS: Dict[str, List[str]] = {
    "gaming": ["game", "gaming", "steam", "playstation", "xbox", "nintendo", "valorant", "minecraft", "roblox", "genshin", "elden ring", "league", "fortnite", "fps", "rpg"],
    "coding & tech": ["code", "coding", "python", "javascript", "developer", "programming", "software", "linux", "github", "bug", "algorithm", "frontend", "backend", "api"],
    "anime & manga": ["anime", "manga", "weeb", "otaku", "cosplay", "jujutsu", "naruto", "one piece", "demon slayer", "bleach", "crunchyroll"],
    "music": ["music", "song", "guitar", "piano", "spotify", "playlist", "band", "album", "singer", "concert", "beat", "melody"],
    "art & design": ["art", "drawing", "illustration", "design", "sketch", "digital art", "blender", "photoshop", "animation"],
    "reading & writing": ["book", "reading", "novel", "fiction", "author", "writing", "story", "poetry", "lore"],
    "fitness & sports": ["gym", "workout", "fitness", "running", "football", "soccer", "basketball", "training", "exercise"],
    "cooking & food": ["cooking", "recipe", "baking", "food", "cook", "coffee", "tea", "chef", "delicious"],
    "science & study": ["science", "physics", "math", "study", "exam", "university", "college", "school", "project", "homework"]
}

# Strict blacklist of sensitive categories (Section 19: Privacy & Safety)
# Kazumi will NEVER extract or store topics related to these categories
SENSITIVE_PATTERNS = [
    r"\b(?:password|passwd|pin|credit card|cvv|bank account|routing number|ssn|social security)\b",
    r"\b(?:republican|democrat|biden|trump|election|politics|communist|fascist|socialist)\b",
    r"\b(?:christianity|islam|muslim|hindu|jewish|religion|atheist|theology|church|mosque|temple)\b",
    r"\b(?:heterosexual|homosexual|gay|lesbian|bisexual|transgender|queer|lgbtq|sexuality)\b",
    r"\b(?:depression|bipolar|schizophrenia|medication|antidepressant|prescription|diagnosis|therapy|psychiatrist|suicide|self harm)\b"
]

LAUGHTER_WORDS = {
    "lol", "lmao", "lmfao", "haha", "hahaha", "hahahaha", "xd", "rofl", "kek", "wheeze",
    "dead", "dying", "nahh", "lmaooo", "loool", "ahahaha"
}

SLANG_WORDS = {
    "u", "r", "ur", "idk", "tbh", "rn", "bc", "wth", "wtf", "imo", "imho", "bruh", "cuz",
    "gonna", "wanna", "yall", "bro", "fr", "frfr", "ngl", "smh", "kinda", "sorta", "dunno",
    "wassup", "sup", "homie", "dude", "fam"
}

FORMAL_WORDS = {
    "however", "therefore", "furthermore", "additionally", "regarding", "appreciate",
    "sincerely", "certainly", "indeed", "consequently", "specifically", "particular",
    "nevertheless", "further", "greetings", "pleasant", "inquire", "assist"
}

SARCASM_MARKERS = [
    r"/s\b",
    r"\bkappa\b",
    r"\b(?:yeah right|oh sure|totally|as if|obviously|clearly|what a surprise|no kidding|genius)\b",
    r'"[\w\s]{2,15}"'  # Quotes around short phrases indicating irony
]

HYPE_WORDS = {
    "omg", "lets go", "let's go", "yooo", "yoooo", "pog", "poggers", "fire", "hype",
    "insane", "crazy", "huge", "w", "massive", "epic", "goated", "goat"
}

ACHIEVEMENT_PATTERNS = [
    r"\b(?:finally (?:finished|got|passed|completed|won|did it))\b",
    r"\b(?:got the job|passed (?:my|the) exam|graduated|won the match|new high score)\b",
    r"\b(?:project is done|reached level|promoted)\b"
]

SAD_PATTERNS = [
    r"\b(?:i'm so sad|feeling down|rough day|bad day|failed my|terrible day|crying|heartbroken|rip)\b",
    r"\b(?:lost my|sadly|exhausted|miss them)\b"
]

EMOJI_REGEX = re.compile(
    r"["
    r"\U0001F600-\U0001F64F"  # emoticons
    r"\U0001F300-\U0001F5FF"  # symbols & pictographs
    r"\U0001F680-\U0001F6FF"  # transport & map
    r"\U0001F1E0-\U0001F1FF"  # flags
    r"\U00002702-\U000027B0"
    r"\U000024C2-\U0001F251"
    r"\U0001F900-\U0001F9FF"  # supplemental symbols
    r"\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
    r"]+",
    flags=re.UNICODE
)

CUSTOM_DISCORD_EMOJI_REGEX = re.compile(r"<a?:\w+:\d+>")


class BehaviourAnalyzer:
    """
    Analyzes message tokens, stylistic cues, and emotional markers.
    Produces an observation snapshot without calling any external API.
    """

    def is_sensitive(self, text: str) -> bool:
        """Checks if text contains private, medical, political, or credential topics."""
        lower = text.lower()
        for pat in SENSITIVE_PATTERNS:
            if re.search(pat, lower):
                return True
        return False

    def count_emojis(self, text: str) -> int:
        """Counts both standard Unicode emojis and custom Discord emojis."""
        unicode_emojis = len(EMOJI_REGEX.findall(text))
        custom_emojis = len(CUSTOM_DISCORD_EMOJI_REGEX.findall(text))
        return unicode_emojis + custom_emojis

    def analyze_formality(self, text: str, words: List[str]) -> float:
        """Computes formality score from 0.0 (very casual/slang) to 1.0 (formal)."""
        if not words:
            return 0.5

        lower_words = [w.lower() for w in words]
        total_words = len(words)

        # 1. Capitalization quality
        starts_capital = bool(text and text[0].isupper())
        proper_i = "I" in words or "I'm" in words or "I've" in words or "I'll" in words
        lowercase_i = "i" in words or "im" in words or "ive" in words

        cap_score = 0.5
        if starts_capital:
            cap_score += 0.25
        if proper_i and not lowercase_i:
            cap_score += 0.25
        elif lowercase_i:
            cap_score -= 0.25

        # 2. Punctuation presence
        has_proper_ending = bool(re.search(r"[.?!]$", text.strip()))
        has_commas = "," in text or ";" in text

        punct_score = 0.3
        if has_proper_ending:
            punct_score += 0.4
        if has_commas:
            punct_score += 0.3

        # 3. Slang vs Formal Lexicon
        slang_hits = sum(1 for w in lower_words if w in SLANG_WORDS)
        formal_hits = sum(1 for w in lower_words if w in FORMAL_WORDS)

        lex_score = 0.5
        if slang_hits > 0:
            lex_score -= min(0.4, (slang_hits / total_words) * 0.8)
        if formal_hits > 0:
            lex_score += min(0.4, (formal_hits / total_words) * 0.8)

        # Blend
        raw = (cap_score * 0.35) + (punct_score * 0.35) + (lex_score * 0.30)
        return max(0.0, min(1.0, raw))

    def analyze_humor(self, text: str, words: List[str]) -> float:
        """Detects humor indicators (laughter tokens, funny emojis, memes)."""
        lower = text.lower()
        lower_words = [w.lower() for w in words]

        score = 0.0

        # Laughter tokens
        laugh_count = sum(1 for w in lower_words if w in LAUGHTER_WORDS)
        if laugh_count > 0:
            score += min(0.6, 0.3 + (laugh_count * 0.15))

        # Funny emojis (😂, 🤣, 💀, 😭 used humorously)
        funny_emojis = len(re.findall(r"[😂🤣💀😹]", text))
        if funny_emojis > 0:
            score += min(0.4, 0.2 + (funny_emojis * 0.1))

        # Meme phrases
        if any(p in lower for p in ["bro really", "skill issue", "caught in 4k", "no way bro", "bro think he"]):
            score += 0.35

        return max(0.0, min(1.0, score))

    def analyze_sarcasm(self, text: str) -> float:
        """Detects sarcasm cues and ironic markers."""
        lower = text.lower()
        score = 0.0

        for pat in SARCASM_MARKERS:
            if re.search(pat, lower):
                score += 0.45

        # Check for eye roll or smirk emojis
        if re.search(r"[🙄😏🙃]", text):
            score += 0.35

        return max(0.0, min(1.0, score))

    def analyze_verbosity(self, words: List[str]) -> float:
        """Maps word count to verbosity score 0.0 - 1.0."""
        count = len(words)
        if count <= 3:
            return 0.1
        if count <= 8:
            return 0.3
        if count <= 20:
            return 0.55
        if count <= 45:
            return 0.75
        return 1.0

    def analyze_emoji_usage(self, text: str, words: List[str]) -> float:
        """Computes emoji density relative to message length."""
        count = self.count_emojis(text)
        if count == 0:
            return 0.0
        word_count = max(1, len(words))
        ratio = count / word_count
        if count >= 3 or ratio > 0.4:
            return 1.0
        if count == 2 or ratio > 0.2:
            return 0.7
        return 0.4

    def analyze_energy(self, text: str, words: List[str]) -> float:
        """Detects energy from capitalization, punctuation, and hype words."""
        if not words:
            return 0.2

        score = 0.2
        # All-caps words (min 2 chars)
        caps_words = sum(1 for w in words if len(w) >= 2 and w.isupper() and w.isalpha())
        if caps_words > 0:
            score += min(0.5, (caps_words / len(words)) * 0.7)

        # Exclamations
        exclamations = text.count("!")
        if exclamations >= 3:
            score += 0.35
        elif exclamations >= 1:
            score += 0.2

        # Hype words
        lower_words = [w.lower() for w in words]
        hype_hits = sum(1 for w in lower_words if w in HYPE_WORDS)
        if hype_hits > 0:
            score += min(0.35, hype_hits * 0.2)

        return max(0.0, min(1.0, score))

    def extract_safe_interests(self, text: str) -> List[str]:
        """Extracts non-sensitive hobbies and topics."""
        if self.is_sensitive(text):
            return []

        lower = text.lower()
        extracted = []
        for category, kws in SAFE_INTEREST_KEYWORDS.items():
            if any(re.search(rf"\b{re.escape(kw)}\b", lower) for kw in kws):
                extracted.append(category)
        return extracted

    def detect_conversation_behaviors(self, text: str, words: List[str], humor: float, formality: float) -> List[str]:
        """Identifies observable conversational behaviors."""
        behaviors = []
        lower = text.lower().strip()

        # Questions
        if "?" in text or any(lower.startswith(q) for q in ["how", "why", "what", "can you", "could you", "is it", "are you", "do you"]):
            behaviors.append("frequently_asks_questions")

        # Explanations
        if len(words) >= 12 and any(p in lower for p in ["because", "due to", "in order to", "for example", "which means", "the reason is"]):
            behaviors.append("gives_detailed_explanations")

        # Joking / Memes
        if humor >= 0.5:
            behaviors.append("likes_joking")

        # Serious / Thoughtful
        if formality >= 0.65 and humor <= 0.2 and "?" not in text:
            behaviors.append("likes_serious_conversations")

        # Short replies vs Long messages
        if len(words) <= 3:
            behaviors.append("short_replies")
        elif len(words) >= 30:
            behaviors.append("long_messages")

        return behaviors

    def detect_emotional_intent(self, text: str) -> Tuple[Optional[str], float]:
        """
        Detects specific emotional situations for reaction intelligence:
        - achievement (e.g. 'finally finished')
        - funny (e.g. 'lmao', hilarious)
        - sad (e.g. 'failed my exam', 'bad day')
        - surprise (e.g. 'wait what', 'no way')
        - agreement (e.g. 'totally agree', 'facts')
        Returns (intent_type, intensity 0.0 - 1.0).
        """
        lower = text.lower()

        # Check Achievement
        for pat in ACHIEVEMENT_PATTERNS:
            if re.search(pat, lower):
                return ("achievement", 0.9)

        # Check Sad
        for pat in SAD_PATTERNS:
            if re.search(pat, lower):
                return ("sad", 0.85)

        # Check Surprise
        if any(p in lower for p in ["wait what", "no way", "holy shit", "wtfff", "are you serious", "are u serious", "no shot"]):
            return ("surprise", 0.8)

        # Check Funny
        funny_markers = sum(1 for w in lower.split() if w in LAUGHTER_WORDS)
        if funny_markers >= 2 or any(e in text for e in ["😂", "🤣", "💀"]):
            return ("funny", 0.85)

        # Check Agreement / Appreciation
        if any(p in lower for p in ["great idea", "looks good", "nice work", "thanks everyone", "agreed", "facts"]):
            return ("agreement", 0.7)

        return (None, 0.0)

    def analyze(self, text: str, context: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Main analysis method for a single message with optional conversation context.
        Returns a structured observation dictionary.
        """
        cleaned_text = (text or "").strip()
        words = re.findall(r"\b[\w']+\b", cleaned_text)

        # Calculate communication dimensions
        formality = self.analyze_formality(cleaned_text, words)
        humor = self.analyze_humor(cleaned_text, words)
        sarcasm = self.analyze_sarcasm(cleaned_text)
        verbosity = self.analyze_verbosity(words)
        emoji_usage = self.analyze_emoji_usage(cleaned_text, words)
        energy = self.analyze_energy(cleaned_text, words)

        # Contextual adjustment: If previous message was funny/joking and user responds 'quit', adjust humor
        if context and len(context) > 0:
            recent_combined = " ".join(context).lower()
            if any(w in recent_combined for w in LAUGHTER_WORDS) and "quit" in cleaned_text.lower():
                humor = max(humor, 0.4)

        behaviors = self.detect_conversation_behaviors(cleaned_text, words, humor, formality)
        safe_interests = self.extract_safe_interests(cleaned_text)
        emotional_intent, emotional_intensity = self.detect_emotional_intent(cleaned_text)

        return {
            "style": {
                "formality": formality,
                "humor": humor,
                "sarcasm": sarcasm,
                "verbosity": verbosity,
                "emoji_usage": emoji_usage,
                "energy": energy
            },
            "behaviors": behaviors,
            "interests": safe_interests,
            "emotional_intent": emotional_intent,
            "emotional_intensity": emotional_intensity,
            "word_count": len(words),
            "char_count": len(cleaned_text)
        }
