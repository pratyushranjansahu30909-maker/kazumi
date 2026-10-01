import os
import sys
import io
import time
import json
import logging
import tempfile
import threading
from typing import Optional

logger = logging.getLogger("TTS_Engine")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_DIR = os.path.join(ROOT_DIR, "portfolio")
VOICES_DIR = os.path.join(ROOT_DIR, "voices")
os.makedirs(VOICES_DIR, exist_ok=True)

if PORTFOLIO_DIR not in sys.path:
    sys.path.append(PORTFOLIO_DIR)

DEFAULT_VOICE_DESIGN_PROMPT = (
    "A cute young adult female anime-inspired AI companion with a soft, bright, warm, and slightly high-pitched voice. "
    "She sounds youthful and friendly without sounding childish. Her voice is naturally expressive, gentle, and slightly playful, "
    "with clear English pronunciation and a smooth conversational rhythm. She has subtle breathiness and a warm emotional tone. "
    "She should sound believable and natural rather than exaggerated or cartoonish. Her voice becomes brighter and more energetic "
    "when excited, softer and gentler when comforting someone, slightly hesitant when embarrassed, and calmer and slower when sad. "
    "Maintain a consistent character voice across conversations."
)

EMOTION_DELIVERY_MAP = {
    "happy": "Bright, energetic, warm and playful delivery.",
    "joyful": "Bright, energetic, warm and playful delivery.",
    "sad": "Soft, slower, quieter and emotionally gentle delivery.",
    "depressed": "Soft, slower, quieter and emotionally gentle delivery.",
    "excited": "Higher energy, slightly faster delivery and brighter expression.",
    "surprised": "Higher energy, slightly faster delivery and brighter expression.",
    "embarrassed": "Soft, hesitant delivery with natural pauses.",
    "shy": "Soft, hesitant delivery with natural pauses.",
    "angry": "Sharper and firmer delivery without excessive shouting.",
    "frustrated": "Sharper and firmer delivery without excessive shouting.",
    "comforting": "Warm, calm, gentle and reassuring delivery.",
    "empathetic": "Warm, calm, gentle and reassuring delivery.",
    "calm": "Warm, conversational and gentle delivery.",
    "default": "Warm, conversational and gentle delivery."
}

class QwenTTSEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(QwenTTSEngine, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.model_name = os.environ.get("TTS_MODEL", "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign")
        self.enabled = os.environ.get("TTS_ENABLED", "false").lower() in ("true", "1", "yes")
        self.device = "cuda" if self._check_cuda_available() else "cpu"
        self.model = None
        self.loading_lock = threading.Lock()
        self.is_loading = False
        self.load_error = None
        self.default_prompt = os.environ.get("VOICE_DESIGN_PROMPT", DEFAULT_VOICE_DESIGN_PROMPT)
        self._synthesis_cache = {}  # Fast in-memory cache for synthesized voice lines

    def _check_cuda_available(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    def load_model(self) -> bool:
        """Loads Qwen3-TTS 1.7B VoiceDesign model into memory with multi-thread CPU optimization."""
        if not self.enabled:
            return False
        if self.model is not None:
            return True
        with self.loading_lock:
            if self.model is not None:
                return True
            try:
                self.is_loading = True
                print(f"[TTS] Model: {self.model_name}")
                print(f"[TTS] Device: {self.device.upper()}")
                print(f"[TTS] Loading weights into memory...")
                
                import torch
                # Maximize CPU intra-op thread parallelism
                if self.device == "cpu":
                    torch.set_num_threads(max(4, os.cpu_count() or 4))
                
                from qwen_tts.inference.qwen3_tts_model import Qwen3TTSModel
                
                self.model = Qwen3TTSModel.from_pretrained(
                    self.model_name,
                    torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
                    device_map="auto" if self.device == "cuda" else None
                )
                print(f"[TTS] Status: Ready")
                logger.info(f"[TTS] Model {self.model_name} initialized on {self.device.upper()}. Status: Ready.")
                self.is_loading = False
                self.load_error = None
                return True
            except Exception as e:
                self.load_error = str(e)
                self.is_loading = False
                print(f"[TTS] ERROR: Failed to load {self.model_name}: {e}")
                logger.error(f"[TTS] Failed to load {self.model_name}: {e}")
                return False


    def build_emotion_prompt(self, base_prompt: Optional[str] = None, emotion: Optional[str] = None) -> str:
        """Constructs emotion-conditioned prompt while maintaining consistent character voice identity."""
        core_prompt = base_prompt or self.default_prompt
        if not emotion:
            return core_prompt
        
        emo_key = emotion.lower().strip()
        delivery = EMOTION_DELIVERY_MAP.get(emo_key, EMOTION_DELIVERY_MAP["default"])
        return f"{core_prompt} Emotional state: [{emo_key.upper()}]. Style instructions: {delivery}"

    def synthesize(
        self,
        text: str,
        voice_prompt: Optional[str] = None,
        emotion: Optional[str] = None,
        language: str = "english"
    ) -> Optional[bytes]:
        """
        Synthesizes speech using exclusively Qwen3-TTS 1.7B VoiceDesign.
        No legacy fallbacks. If Qwen fails or is unavailable, raises/logs clear error.
        """
        if not self.enabled:
            return None

        if not text or not text.strip():
            return None

        clean_text = text.replace("*", "").strip()
        if not clean_text:
            return None

        if not self.model:
            if not self.load_model():
                return None

        full_prompt = self.build_emotion_prompt(voice_prompt, emotion)
        emotion_tag = emotion.upper() if emotion else "NATURAL"
        
        # Map common 2-letter codes to Qwen supported language strings
        lang_map = {
            "en": "english",
            "zh": "chinese",
            "ja": "japanese",
            "fr": "french",
            "de": "german",
            "it": "italian",
            "ko": "korean",
            "pt": "portuguese",
            "ru": "russian",
            "es": "spanish"
        }
        lang_clean = lang_map.get(language.lower(), language.lower())
        if lang_clean not in ('auto', 'chinese', 'english', 'french', 'german', 'italian', 'japanese', 'korean', 'portuguese', 'russian', 'spanish'):
            lang_clean = "english"

        # Check in-memory synthesis cache for instant retrieval
        import hashlib
        cache_key = hashlib.md5(f"{clean_text}:{full_prompt}:{lang_clean}".encode("utf-8")).hexdigest()
        if cache_key in self._synthesis_cache:
            logger.info(f"[TTS Cache Hit] Returning cached audio for '{clean_text[:30]}...' (0ms)")
            return self._synthesis_cache[cache_key]

        print(f"[VOICE] Generating speech with Qwen3-TTS VoiceDesign | Emotion: {emotion_tag} | Language: {lang_clean}")
        logger.info(f"[VOICE] Generating speech with Qwen3-TTS VoiceDesign | Emotion: {emotion_tag} | Prompt: {full_prompt[:60]}...")
        
        start_time = time.time()
        try:
            wavs, sr = self.model.generate_voice_design(
                text=clean_text,
                instruct=full_prompt,
                language=lang_clean,
                do_sample=True,
                temperature=0.85,
                top_p=0.95
            )

            if wavs and len(wavs) > 0:
                audio_np = wavs[0]
                import soundfile as sf
                import numpy as np

                # Peak normalization
                max_val = np.max(np.abs(audio_np))
                if max_val > 0:
                    audio_np = (audio_np / max_val) * 0.95

                buf = io.BytesIO()
                sf.write(buf, audio_np, sr, format='WAV', subtype='PCM_16')
                audio_bytes = buf.getvalue()
                
                elapsed_ms = int((time.time() - start_time) * 1000)
                logger.info(f"[TTS] Generated {len(audio_bytes)} bytes WAV in {elapsed_ms}ms with Qwen3-TTS VoiceDesign.")
                
                if len(self._synthesis_cache) > 100:
                    self._synthesis_cache.clear()
                self._synthesis_cache[cache_key] = audio_bytes
                
                return audio_bytes
            else:
                raise ValueError("Qwen3-TTS VoiceDesign returned empty waveform audio.")
        except Exception as e:
            logger.error(f"[TTS Error] Qwen3-TTS synthesis failed: {e}")
            raise e



# Global Engine Instance
_engine = QwenTTSEngine()

def init_tts() -> bool:
    """Initializes and pre-loads the Qwen3-TTS engine on startup."""
    print(f"[TTS] Model: {_engine.model_name}")
    print(f"[TTS] Device: {_engine.device.upper()}")
    success = _engine.load_model()
    if success:
        print(f"[TTS] Status: Ready")
    else:
        print(f"[TTS] Status: Offline ({_engine.load_error})")
    return success

def is_tts_enabled() -> bool:
    """Returns whether TTS is currently active and loaded."""
    return _engine.enabled and (_engine.model is not None)

def get_tts_engine() -> QwenTTSEngine:
    """Returns the singleton QwenTTSEngine instance."""
    return _engine

def speak(
    text: str,
    voice_prompt: Optional[str] = None,
    emotion: Optional[str] = None,
    play_audio_immediately: bool = False,
    output_path: Optional[str] = None
) -> Optional[str]:
    """
    Synthesizes speech using exclusively Qwen3-TTS 1.7B VoiceDesign and returns WAV file path.
    """
    if not _engine.enabled or not text or not text.strip():
        return None

    audio_bytes = _engine.synthesize(text, voice_prompt=voice_prompt, emotion=emotion)
    if not audio_bytes:
        return None

    if not output_path:
        fd, output_path = tempfile.mkstemp(prefix="kazumi_qwen_", suffix=".wav")
        os.close(fd)

    with open(output_path, "wb") as f:
        f.write(audio_bytes)

    if play_audio_immediately:
        try:
            _play_audio_file(output_path)
        except Exception as play_err:
            logger.warning(f"[TTS Playback Error]: {play_err}")

    return output_path

def _play_audio_file(wav_path: str):
    """Immediate cross-platform audio playback helper."""
    if os.name == 'nt':
        try:
            import winsound
            winsound.PlaySound(wav_path, winsound.SND_FILENAME | winsound.SND_ASYNC)
            return
        except Exception:
            pass
    try:
        import subprocess
        if sys.platform == "darwin":
            subprocess.Popen(["afplay", wav_path])
        elif sys.platform.startswith("linux"):
            subprocess.Popen(["aplay", wav_path])
    except Exception:
        pass
