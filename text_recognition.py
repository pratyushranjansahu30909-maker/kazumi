#!/usr/bin/env python3
"""
🌸 Kazumi Text Recognition System (OCR & Document Vision)
Enables Kazumi to see, extract, transcribe, and understand text from images, screenshots,
handwritten notes, memes, documents, and code files.
"""

import os
import io
import sys
import base64
import logging
from typing import Optional, Union, Dict, Any

logger = logging.getLogger("TextRecognition")

# Try to load API_KEY from environment or .env
API_KEY = os.environ.get("API_KEY", "")
if not API_KEY:
    for env_path in [".env", "portfolio/.env", "../.env"]:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            if k.strip() == "API_KEY":
                                API_KEY = v.strip().strip('"').strip("'")
                                break
            except Exception:
                pass
        if API_KEY:
            break

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class TextRecognitionEngine:
    """
    High-precision Text Recognition & Vision Engine for Kazumi.
    Extracts text from screenshots, photos, documents, and code with deep context awareness.
    """
    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(TextRecognitionEngine, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, api_key: Optional[str] = None):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.api_key = api_key or API_KEY
        self.client = None
        self._init_client()

    def _init_client(self):
        if OPENAI_AVAILABLE and self.api_key:
            try:
                self.client = OpenAI(api_key=self.api_key)
                logger.info("🌸 Text Recognition Engine initialized with OpenAI Vision.")
            except Exception as e:
                logger.warning(f"Could not initialize OpenAI client for Text Recognition: {e}")
                self.client = None

    def is_available(self) -> bool:
        """Returns True if the recognition engine is ready to transcribe images."""
        return bool(OPENAI_AVAILABLE and self.client is not None and self.api_key)

    def extract_text_from_bytes(
        self,
        data: bytes,
        filename: str = "",
        mime_type: str = "image/png",
        user_query: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Extracts and transcribes text from raw bytes (image or text document).
        Returns a dict with extracted text, character count, and metadata.
        """
        fname_lower = (filename or "").lower()

        # 1. Check if plain text / code document
        text_extensions = (
            ".txt", ".md", ".csv", ".json", ".log", ".py", ".js", ".ts",
            ".html", ".css", ".yaml", ".yml", ".xml", ".ini", ".conf", ".sql", ".sh"
        )
        if any(fname_lower.endswith(ext) for ext in text_extensions) or mime_type.startswith("text/"):
            try:
                decoded_text = data.decode("utf-8", errors="replace").strip()
                return {
                    "success": True,
                    "text": decoded_text,
                    "filename": filename,
                    "type": "document",
                    "char_count": len(decoded_text),
                    "summary": f"Decoded {len(decoded_text)} characters from {filename or 'document'}."
                }
            except Exception as doc_err:
                logger.error(f"Error decoding text document: {doc_err}")

        # 2. Check if image file
        image_extensions = (".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff")
        is_image = any(fname_lower.endswith(ext) for ext in image_extensions) or mime_type.startswith("image/")

        if not is_image and not mime_type.startswith("image/"):
            # Attempt to decode as text if possible
            try:
                decoded = data.decode("utf-8")
                return {
                    "success": True,
                    "text": decoded,
                    "filename": filename,
                    "type": "document",
                    "char_count": len(decoded),
                    "summary": f"Decoded text file ({len(decoded)} chars)."
                }
            except UnicodeDecodeError:
                pass

        if not self.is_available():
            return {
                "success": False,
                "text": "",
                "error": "Text recognition vision engine is currently offline (API key required).",
                "filename": filename,
                "type": "image"
            }

        # Determine proper mime type
        if fname_lower.endswith(".jpg") or fname_lower.endswith(".jpeg"):
            mime_type = "image/jpeg"
        elif fname_lower.endswith(".webp"):
            mime_type = "image/webp"
        elif fname_lower.endswith(".gif"):
            mime_type = "image/gif"
        elif fname_lower.endswith(".png"):
            mime_type = "image/png"

        try:
            b64_str = base64.b64encode(data).decode("utf-8")
            data_url = f"data:{mime_type};base64,{b64_str}"

            if user_query and user_query.strip():
                vision_instruction = (
                    f"You are Kazumi's optical text recognition assistant. First, extract all readable text verbatim "
                    f"from this image. Then, address the user's specific request: '{user_query.strip()}'.\n"
                    f"Format cleanly with the transcribed text clearly marked."
                )
            else:
                vision_instruction = (
                    "You are Kazumi's optical character recognition (OCR) and text recognition system. "
                    "Extract and transcribe all visible text in this image accurately and verbatim. "
                    "Include printed text, handwriting, signs, screen code, and captions. "
                    "Preserve paragraph layout and line breaks. "
                    "If the image contains absolutely no readable text, reply with: [NO_TEXT_DETECTED] followed by a brief description of what is in the image."
                )

            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": vision_instruction},
                        {"type": "image_url", "image_url": {"url": data_url, "detail": "high"}}
                    ]
                }
            ]

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=800,
                temperature=0.2
            )

            result_text = response.choices[0].message.content.strip()

            has_text = "[NO_TEXT_DETECTED]" not in result_text
            clean_result = result_text.replace("[NO_TEXT_DETECTED]", "").strip()

            return {
                "success": True,
                "text": clean_result,
                "has_text": has_text,
                "filename": filename,
                "type": "image",
                "char_count": len(clean_result),
                "summary": f"Recognized {len(clean_result)} characters from image {filename}." if has_text else "No text detected in image."
            }

        except Exception as e:
            logger.error(f"Vision OCR failed on image: {e}", exc_info=True)
            return {
                "success": False,
                "text": "",
                "error": str(e),
                "filename": filename,
                "type": "image"
            }

    def recognize_file(self, filepath: str, user_query: Optional[str] = None) -> Dict[str, Any]:
        """Reads a local file path and performs text recognition."""
        if not os.path.exists(filepath):
            return {"success": False, "error": f"File not found: {filepath}"}
        try:
            with open(filepath, "rb") as f:
                data = f.read()
            return self.extract_text_from_bytes(data, filename=os.path.basename(filepath), user_query=user_query)
        except Exception as e:
            return {"success": False, "error": str(e)}


# Global singleton helper
_recognition_engine = None

def get_text_recognition_engine() -> TextRecognitionEngine:
    global _recognition_engine
    if _recognition_engine is None:
        _recognition_engine = TextRecognitionEngine()
    return _recognition_engine
