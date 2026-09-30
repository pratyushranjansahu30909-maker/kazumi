import os
import re
from skills.base_skill import KazumiSkill
from text_recognition import get_text_recognition_engine

class TextRecognitionSkill(KazumiSkill):
    """
    Skill for recognizing and reading text from images, documents, and screenshots.
    """

    def get_triggers(self):
        return [
            r"^(?:recognize|extract|read|scan|transcribe)\s+(?:text|image|screenshot|ocr)\b",
            r"^ocr\b",
            r"\b(?:what does (?:this|the) (?:image|picture|screenshot|photo) say)\b",
            r"\bread the text (?:in|from|on)\b"
        ]

    def get_help(self):
        return "ocr <filepath/image>", "Recognize and transcribe text from an image or document using AI vision."

    def handle(self, text, clean_text, valence):
        engine = get_text_recognition_engine()
        if not engine.is_available():
            return "My text recognition vision engine is currently offline. Please ensure an API key is configured! 🌸"

        # Look for file paths in the prompt
        filepath_match = re.search(r'(?:file|path|image|from|in)?\s*[:=]?\s*([A-Za-z0-9_\-\\/:\.]+\.(?:png|jpg|jpeg|webp|bmp|gif|txt|log|pdf|md))', text, re.IGNORECASE)
        
        if filepath_match:
            candidate_path = filepath_match.group(1).strip()
            if os.path.exists(candidate_path):
                res = engine.recognize_file(candidate_path)
                if res.get("success"):
                    recognized = res.get("text", "")
                    if recognized:
                        return f"(Kazumi reads through the text carefully...) 🌸\n\n**Here is what I recognized:**\n```\n{recognized}\n```"
                    else:
                        return "(Kazumi looks closely at the image...) I checked the image, but I couldn't spot any readable text in it! 🌸"
                else:
                    return f"I had a little trouble reading that file: {res.get('error', 'unknown error')} 🌸"

        return "To recognize text, you can upload an image in Discord, use `/ocr`, or mention an image path! 🌸"
