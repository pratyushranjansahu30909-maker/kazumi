import re
import json

class EmotionalEngine:
    EMOTIONS = [
        "happy", "excited", "sad", "shy", "affectionate",
        "curious", "playful", "caring", "frustrated", "neutral"
    ]
    
    KEYWORDS = {
        "happy": ["happy", "joy", "joyful", "cheerful", "content", "glad", "smile", "laugh", "great", "wonderful", "amazing", "good"],
        "excited": ["excited", "thrilled", "ecstatic", "yippee", "wow", "hype", "awesome", "fantastic", "cant wait", "can't wait"],
        "sad": ["sad", "lonely", "depressed", "hurt", "sorrow", "unhappy", "cry", "weeping", "down", "blue", "pain", "grief"],
        "shy": ["shy", "embarrassed", "blush", "bashful", "quiet", "timid", "nervous", "blushing", "baka", "giggle"],
        "affectionate": ["love", "loved", "adore", "cherish", "sweetie", "darling", "honey", "babe", "precious", "heart", "hug", "kiss"],
        "curious": ["what", "why", "how", "who", "where", "when", "wonder", "explain", "question", "ask", "query"],
        "playful": ["playful", "fun", "game", "tease", "joke", "giggles", "cheeky", "meow", "catgirl", "prank", "play"],
        "caring": ["care", "worry", "protect", "help", "soothe", "heal", "kind", "safe", "relax", "calm", "breathe", "comfort"],
        "frustrated": ["frustrated", "angry", "annoyed", "irritated", "mad", "rage", "jealous", "pout", "sulk", "disappointed"]
    }

    def __init__(self):
        # Session states to keep emotional continuity
        self.session_states = {}

    def get_session_state(self, session_id):
        if not session_id:
            session_id = "default"
        if session_id not in self.session_states:
            self.session_states[session_id] = {e: 0.0 for e in self.EMOTIONS}
            self.session_states[session_id]["neutral"] = 1.0
        return self.session_states[session_id]

    def set_session_state(self, session_id, state):
        if not session_id:
            session_id = "default"
        self.session_states[session_id] = state

    def analyze(self, text, session_id=None):
        clean_text = text.lower().strip()
        words = re.findall(r"\b\w+\b", clean_text)
        
        # Calculate raw current scores
        current_scores = {e: 0.0 for e in self.EMOTIONS}
        
        matched_any = False
        for emotion, keywords in self.KEYWORDS.items():
            matches = sum(1 for w in words if w in keywords)
            if matches > 0:
                current_scores[emotion] = min(1.0, matches * 0.4)
                matched_any = True
                
        if not matched_any:
            current_scores["neutral"] = 0.8
            
        # Get previous state for continuity
        prev_state = self.get_session_state(session_id)
        
        # Continuity blend: 70% current, 30% previous
        blended = {}
        for e in self.EMOTIONS:
            blended[e] = (0.7 * current_scores[e]) + (0.3 * prev_state.get(e, 0.0))
            
        # Save state back for the next turn
        self.set_session_state(session_id, blended)
        
        # Sort scores to get primary and secondary emotions
        sorted_emotions = sorted(
            [(e, score) for e, score in blended.items() if e != "neutral"],
            key=lambda x: x[1],
            reverse=True
        )
        
        primary = "neutral"
        secondary = "neutral"
        primary_score = blended.get("neutral", 0.0)
        
        if sorted_emotions and sorted_emotions[0][1] > 0.1:
            primary = sorted_emotions[0][0]
            primary_score = sorted_emotions[0][1]
            if len(sorted_emotions) > 1 and sorted_emotions[1][1] > 0.15:
                secondary = sorted_emotions[1][0]
        
        # Calculate final scaled intensity (0.0 to 1.0)
        intensity = round(max(0.4, min(1.0, primary_score * 1.2)), 2)
        
        return {
            "primary_emotion": primary,
            "secondary_emotion": secondary,
            "intensity": intensity
        }
