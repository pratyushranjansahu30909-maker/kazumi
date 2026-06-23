import os
import sys

# Voice Lock Profile Configuration
VOICE_PROFILE = {
    "voice_name": "Kazumi",
    "speaker_id": "kazumi_female",
    "reference_audio": "voices/reference_voice.wav",
    "voice_locked": True
}

# 🎀 Cute Anime Companion Voice Tuning Settings
VOICE_TUNING = {
    "brightness": 1.15,
    "warmth": 1.05,
    "expressiveness": 1.20,
    "energy": 1.10,
    "pitch_offset": 2,
    "clarity": 1.15
}

# Exact transcript of the first 6.0 seconds of the voices/reference_voice.wav file
VOICE_PROMPT_TEXT = "Are you trying to scare me or just being dramatic? Seriously, are you okay?"

def get_locked_profile():
    return dict(VOICE_PROFILE)

def get_tuning():
    return dict(VOICE_TUNING)

def get_absolute_reference_path():
    root_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    orig_path = os.path.join(root_path, "voices", "reference_voice.wav")
    sliced_path = os.path.join(root_path, "voices", "reference_voice_sliced.wav")
    
    # Generate 6.0 second sliced version if it doesn't exist
    if not os.path.exists(sliced_path) and os.path.exists(orig_path):
        import wave
        try:
            with wave.open(orig_path, "rb") as w_in:
                params = w_in.getparams()
                framerate = w_in.getframerate()
                # Slice first 6.0 seconds
                n_frames = int(framerate * 6.0)
                frames = w_in.readframes(n_frames)
                with wave.open(sliced_path, "wb") as w_out:
                    w_out.setparams(params)
                    w_out.writeframes(frames)
        except Exception:
            return os.path.abspath(orig_path)
            
    if os.path.exists(sliced_path):
        return os.path.abspath(sliced_path)
    return os.path.abspath(orig_path)
