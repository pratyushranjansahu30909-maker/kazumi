import os
import logging
# pyrefly: ignore [missing-import]
import logging_config
logger = logging.getLogger("kazumi_memory")
import re
import time
import json
from kazumi_data import LEXICON

class CozyProfileDict(dict):
    def __setitem__(self, key, value):
        if key == "cozy_points":
            old_value = self.get("cozy_points", 0)
            if value > old_value:
                gain = value - old_value
                # Cozy points are 10 times harder to earn now (10% of standard gain, min 1)
                scaled_gain = max(1, int(gain * 0.1))
                value = old_value + scaled_gain
        super().__setitem__(key, value)

class ChromaMemory:
    """
    A 100% compatible, pure-python persistent JSON memory database.
    Replaces ChromaDB to completely eliminate third-party warnings and compatibility crashes on Python 3.14.
    Supports persistent storage, speakers, valence, and keyword-overlap semantic memory recall.
    """
    def __init__(self, persist_directory="isa_memory"):
        self.persist_path = os.path.join(persist_directory, "conversations.json")
        self.profile_path = os.path.join(persist_directory, "profile.json")
        self.diary_path = os.path.join(persist_directory, "diary.json")
        if not os.path.exists(persist_directory):
            try:
                os.makedirs(persist_directory)
            except Exception:
                pass
        self.history = self.load_history()
        self.profile = self.load_profile()

    def _atomic_write_json(self, file_path, data):
        try:
            # Step 1: Pre-write backup to .bak
            if os.path.exists(file_path):
                import shutil
                shutil.copy2(file_path, file_path + ".bak")
            
            # Step 2: Write atomically to .tmp
            tmp_path = file_path + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            
            # Step 3: Atomic replacement
            os.replace(tmp_path, file_path)
            return True
        except Exception as e:
            tmp_path = file_path + ".tmp"
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass
            raise e

    def load_profile(self):
        profile = None
        diary = None
        
        def attempt_read(path):
            if os.path.exists(path) and os.path.getsize(path) > 0:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            raise FileNotFoundError()

        # Attempt 1: Read main profile
        try:
            profile = attempt_read(self.profile_path)
        except Exception:
            # If main exists but failed (corruption), archive it
            if os.path.exists(self.profile_path):
                corrupted_path = f"{self.profile_path}.corrupted.{int(time.time())}"
                try:
                    os.rename(self.profile_path, corrupted_path)
                except Exception:
                    pass
            
            # Attempt 2: Read backup
            try:
                profile = attempt_read(self.profile_path + ".bak")
            except Exception:
                pass

        # Attempt to read diary
        try:
            diary = attempt_read(self.diary_path)
        except Exception:
            if os.path.exists(self.diary_path):
                corrupted_path = f"{self.diary_path}.corrupted.{int(time.time())}"
                try:
                    os.rename(self.diary_path, corrupted_path)
                except Exception:
                    pass
            try:
                diary = attempt_read(self.diary_path + ".bak")
            except Exception:
                pass

        if not profile:
            profile = self.get_default_profile()
            
        # Migrate old diary entries from profile to diary.json if necessary (Phase 6)
        if diary is None:
            if "diary" in profile and isinstance(profile["diary"], list):
                diary = profile["diary"]
                try:
                    self._atomic_write_json(self.diary_path, diary)
                except Exception:
                    pass
            else:
                diary = []

        profile["diary"] = diary

        if profile.get("name") == "Sweetie":
            profile["name"] = "Friend"
            
        defaults = {
            "_schema_version": 1,
            "_is_default": False,
            "name": "Friend",
            "favorite_drink": "None",
            "birthday": "None",
            "hobbies": [],
            "affection_level": 50,
            "gifts_given": {},
            "diary": [],
            "cozy_points": 100,
            "room_decorations": [],
            "unlocked_photos": [],
            "achievements": [],
            "character": "kazumi",
            "quests": {
                "active": [
                    {"id": "chat", "desc": "Chat with Kazumi (5 messages)", "target": 5, "progress": 0, "points": 20},
                    {"id": "gift", "desc": "Give a sweet gift", "target": 1, "progress": 0, "points": 30},
                    {"id": "game", "desc": "Win any mini-game", "target": 1, "progress": 0, "points": 40}
                ],
                "last_update": time.time()
            },
            "psychology": {
                "avg_word_count": 10.0,
                "msg_count": 0,
                "dominant_vibe": "Neutral",
                "interaction_preference": "Casual Conversation",
                "rolling_valence": 0.0
            },
            "zodiac": "None",
            "horoscope_date": "None",
            "baked_inventory": {}
        }
        for k, v in defaults.items():
            if k not in profile:
                profile[k] = v
        logger.info("Loaded profile with affection_level=%s", profile.get("affection_level"))
        return CozyProfileDict(profile)

    def get_default_profile(self):
        return {
            "_schema_version": 1,
            "_is_default": True,
            "name": "Friend",
            "favorite_drink": "None",
            "birthday": "None",
            "hobbies": [],
            "affection_level": 50,
            "gifts_given": {},
            "diary": [],
            "cozy_points": 100,
            "room_decorations": [],
            "unlocked_photos": [],
            "achievements": [],
            "quests": {
                "active": [
                    {"id": "chat", "desc": "Chat with Kazumi (5 messages)", "target": 5, "progress": 0, "points": 20},
                    {"id": "gift", "desc": "Give a sweet gift", "target": 1, "progress": 0, "points": 30},
                    {"id": "game", "desc": "Win any mini-game", "target": 1, "progress": 0, "points": 40}
                ],
                "last_update": time.time()
            },
            "psychology": {
                "avg_word_count": 10.0,
                "msg_count": 0,
                "dominant_vibe": "Neutral",
                "interaction_preference": "Casual Conversation",
                "rolling_valence": 0.0
            },
            "zodiac": "None",
            "horoscope_date": "None",
            "baked_inventory": {}
        }

    def save_profile(self):
        try:
            logger.info("Saving profile with affection_level=%s", self.profile.get("affection_level"))
            if self.profile and isinstance(self.profile, dict) and "cozy_points" in self.profile:
                if self.profile.get("_is_default"):
                    self.profile["_is_default"] = False
                
                # Split storage: write diary to diary.json and profile without diary key to profile.json
                diary = self.profile.get("diary", [])
                self._atomic_write_json(self.diary_path, diary)
                
                profile_to_save = dict(self.profile)
                if "diary" in profile_to_save:
                    del profile_to_save["diary"]
                    
                self._atomic_write_json(self.profile_path, profile_to_save)
        except Exception:
            pass

    def load_history(self):
        logger.info("Loading conversation history from %s", self.persist_path)
        
        def attempt_read(path):
            if os.path.exists(path) and os.path.getsize(path) > 0:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            raise FileNotFoundError()

        # Attempt 1: Read main conversations.json
        try:
            return attempt_read(self.persist_path)
        except Exception:
            # If main exists but failed (corruption), archive it
            if os.path.exists(self.persist_path):
                corrupted_path = f"{self.persist_path}.corrupted.{int(time.time())}"
                try:
                    os.rename(self.persist_path, corrupted_path)
                except Exception:
                    pass
            
            # Attempt 2: Read backup
            try:
                return attempt_read(self.persist_path + ".bak")
            except Exception:
                pass
        return []

    def save_history(self):
        try:
            if isinstance(self.history, list):
                self._atomic_write_json(self.persist_path, self.history)
        except Exception:
            pass

    def add(self, text, speaker="user", valence=0.0, session_id=None):
        if session_id is None:
            session_id = getattr(self, "current_session_id", None)
        self.history.append({
            "text": text,
            "speaker": speaker,
            "valence": float(valence),
            "timestamp": time.time(),
            "session_id": session_id
        })
        logger.info("Appending to history: %s", text[:30])
        self.save_history()

    def recall(self, text, top_k=3, speaker_filter=None):
        query_words = set(re.findall(r"\b\w+\b", text.lower()))
        if not query_words:
            matching = [item["text"] for item in self.history if not speaker_filter or item["speaker"] == speaker_filter]
            return matching[-top_k:] if matching else []
            
        scored_docs = []
        for item in self.history:
            if speaker_filter and item["speaker"] != speaker_filter:
                continue
            doc_words = set(re.findall(r"\b\w+\b", item["text"].lower()))
            overlap = len(query_words.intersection(doc_words))
            if overlap > 0:
                scored_docs.append((overlap, item["text"]))
                
        scored_docs.sort(key=lambda x: x[0], reverse=True)
        results = [doc[1] for doc in scored_docs[:top_k]]
        
        if not results:
            matching = [item["text"] for item in self.history if not speaker_filter or item["speaker"] == speaker_filter]
            results = matching[-top_k:] if matching else []
            
        return results


class EmotionalEmbedding:
    negators = {"not", "never", "no", "barely", "hardly"}

    def __init__(self):
        self.lexicon = LEXICON

    def valence(self, text):
        words = re.findall(r"\b\w+\b", text.lower())
        scores = []

        for i, w in enumerate(words):
            if w in self.lexicon:
                s = self.lexicon[w]
                if i > 0 and words[i - 1] in self.negators:
                    s = -s
                scores.append(s)

        return sum(scores) / len(scores) if scores else 0.0
