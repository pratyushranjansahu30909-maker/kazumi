import os
import io
import sys
import time
import hashlib
import logging
import threading
from typing import Optional

logger = logging.getLogger("STT_Engine")

ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

class FasterWhisperEngine:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(FasterWhisperEngine, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        self.model_size = os.environ.get("STT_MODEL", "base.en" if os.environ.get("STT_LANG", "en") == "en" else "base")
        self.enabled = os.environ.get("STT_ENABLED", "false").lower() in ("true", "1", "yes")
        self.device = "cuda" if self._check_cuda_available() else "cpu"
        self.compute_type = "float16" if self.device == "cuda" else "int8"
        self.model = None
        self.loading_lock = threading.Lock()
        self.load_error = None
        self.cpu_threads = max(4, os.cpu_count() or 4)
        self._transcribe_cache = {}  # Fast in-memory cache for repeated audio packets

    def _check_cuda_available(self) -> bool:
        try:
            import torch
            return torch.cuda.is_available()
        except Exception:
            return False

    def load_model(self) -> bool:
        """Loads Faster-Whisper model once into memory with multi-threaded CPU/CUDA optimization."""
        if not self.enabled:
            return False
        if self.model is not None:
            return True
        with self.loading_lock:
            if self.model is not None:
                return True
            try:
                print(f"[STT] Model: faster-whisper ({self.model_size})")
                print(f"[STT] Device: {self.device.upper()} ({self.compute_type}) | CPU Threads: {self.cpu_threads}")
                print(f"[STT] Loading faster-whisper weights...")
                
                from faster_whisper import WhisperModel
                self.model = WhisperModel(
                    self.model_size,
                    device=self.device,
                    compute_type=self.compute_type,
                    cpu_threads=self.cpu_threads,
                    num_workers=2
                )
                print(f"[STT] Status: Ready (High-Speed VAD Active)")
                logger.info(f"[STT] Model faster-whisper ({self.model_size}) ready on {self.device.upper()}.")
                self.load_error = None
                return True
            except Exception as e:
                self.load_error = str(e)
                print(f"[STT] Notice: faster-whisper deferred ({e}). Web Audio STT active.")
                logger.info(f"[STT] Initialization deferred: {e}")
                return False

    def transcribe(self, audio_bytes: bytes, language: str = "en") -> Optional[str]:
        """
        High-speed audio transcription
        Transcribes an in-memory audio buffer (WAV/WEBM/OGG) using faster-whisper.
        """
        if not self.enabled:
            return None

        if not audio_bytes or len(audio_bytes) < 100:
            return None

        # Check in-memory hash cache for zero-latency instant recognition
        audio_hash = hashlib.md5(audio_bytes[:2048]).hexdigest()
        if audio_hash in self._transcribe_cache:
            cached_text, cached_time = self._transcribe_cache[audio_hash]
            if time.time() - cached_time < 60:
                return cached_text

        if not self.model:
            if not self.load_model():
                return None

        try:
            print(f"[STT] Speech detected | Transcribing...")
            start_time = time.time()
            
            import soundfile as sf
            import librosa
            import numpy as np

            buffer = io.BytesIO(audio_bytes)
            try:
                audio_np, sr = sf.read(buffer)
                if audio_np.ndim > 1:
                    audio_np = np.mean(audio_np, axis=1)
                if sr != 16000:
                    audio_np = librosa.resample(audio_np, orig_sr=sr, target_sr=16000)
            except Exception:
                buffer.seek(0)
                audio_np, sr = librosa.load(buffer, sr=16000)

            if audio_np.dtype != np.float32:
                audio_np = audio_np.astype(np.float32)

            # High-Speed Greedy Decoding (beam_size=1 is ~4x faster than beam_size=5)
            segments, info = self.model.transcribe(
                audio_np,
                language=language if not self.model_size.endswith(".en") else None,
                beam_size=1,
                best_of=1,
                temperature=0.0,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=250,
                    speech_pad_ms=150,
                    threshold=0.45
                )
            )

            text_parts = [seg.text.strip() for seg in segments if seg.text.strip()]
            final_text = " ".join(text_parts).strip()
            
            elapsed_ms = int((time.time() - start_time) * 1000)
            print(f"[STT] Result: '{final_text}' (Latency: {elapsed_ms}ms)")
            logger.info(f"[STT] Transcribed in {elapsed_ms}ms: '{final_text}'")

            # Cache result
            if final_text:
                if len(self._transcribe_cache) > 200:
                    self._transcribe_cache.clear()
                self._transcribe_cache[audio_hash] = (final_text, time.time())

            return final_text
        except Exception as e:
            logger.warning(f"[STT] Transcription error: {e}")
            return None



# Global STT Instance
_stt_engine = FasterWhisperEngine()

def init_stt() -> bool:
    """Initializes and pre-loads the faster-whisper STT engine."""
    return _stt_engine.load_model()

def transcribe_audio(audio_bytes: bytes, language: str = "en") -> Optional[str]:
    """Transcribes audio using the FasterWhisper engine."""
    return _stt_engine.transcribe(audio_bytes, language=language)

def get_stt_engine() -> FasterWhisperEngine:
    return _stt_engine
