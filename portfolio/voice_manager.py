import os
import sys
import json
import asyncio

ROOT_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VOICES_DIR = os.path.join(ROOT_PATH, "voices")
os.makedirs(VOICES_DIR, exist_ok=True)

# Voice Profiles Configuration Database
VOICE_PROFILES = {
    "default": {
        "voice_id": "default",
        "voice_name": "Kazumi (Childish Playful VTuber Voice)",
        "reference_audio": "voices/user_voice_ref_cute.wav",
        "prompt_text": "Thank you everyone for letting me be your little shark.",
        "voice_locked": True,
        "tuning": {
            "brightness": 1.45,
            "warmth": 0.90,
            "expressiveness": 1.45,
            "energy": 1.20,
            "pitch_offset": 3.2,
            "speed_factor": 1.08,
            "clarity": 1.35
        }
    },
    "vtuber_cute": {
        "voice_id": "vtuber_cute",
        "voice_name": "Kazumi (Childish Playful VTuber Voice)",
        "reference_audio": "voices/user_voice_ref_cute.wav",
        "prompt_text": "Thank you everyone for letting me be your little shark.",
        "voice_locked": True,
        "tuning": {
            "brightness": 1.50,
            "warmth": 0.90,
            "expressiveness": 1.50,
            "energy": 1.25,
            "pitch_offset": 3.5,
            "speed_factor": 1.10,
            "clarity": 1.40
        }
    },
    "mature_calm": {
        "voice_id": "mature_calm",
        "voice_name": "Kazumi (Replicated Voice Calm)",
        "reference_audio": "voices/user_voice_ref_clear.wav",
        "prompt_text": "I have one final project to share with you and I can't wait for you to see it.",
        "voice_locked": True,
        "tuning": {
            "brightness": 1.10,
            "warmth": 1.00,
            "expressiveness": 1.10,
            "energy": 0.95,
            "pitch_offset": 0,
            "speed_factor": 1.0,
            "clarity": 1.25
        }
    },
    "gawr_gura": {
        "voice_id": "gawr_gura",
        "voice_name": "Kazumi (Replicated Voice Expressive)",
        "reference_audio": "voices/user_voice_ref_cute.wav",
        "prompt_text": "Thank you everyone for letting me be your little shark.",
        "voice_locked": True,
        "tuning": {
            "brightness": 1.45,
            "warmth": 0.90,
            "expressiveness": 1.45,
            "energy": 1.20,
            "pitch_offset": 3.2,
            "speed_factor": 1.08,
            "clarity": 1.35
        }
    }
}

def process_vtuber_audio(audio_bytes, pitch_shift_steps=0.0, speed_factor=1.0):
    try:
        import io
        import soundfile as sf
        import numpy as np
        
        buffer = io.BytesIO(audio_bytes)
        data, sr = sf.read(buffer)
        
        # Gentle peak normalization to 0.95 for warm, natural clarity
        max_val = np.max(np.abs(data))
        if max_val > 0:
            data = (data / max_val) * 0.95
            
        out_buf = io.BytesIO()
        sf.write(out_buf, data, sr, format='WAV', subtype='PCM_16')
        return out_buf.getvalue()
    except Exception as e:
        print(f"[Audio Mastering Note]: {e}")
        return audio_bytes

def get_active_profile_id():
    config_path = os.path.join(VOICES_DIR, "active_profile.json")
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                profile_id = data.get("active_profile_id", "default")
                if profile_id in VOICE_PROFILES:
                    return profile_id
        except Exception:
            pass
    return "default"

def generate_mature_calm_ref_sync():
    return True

def generate_default_ref_sync():
    return True


def write_active_voice_cache(profile_id):
    cache_path = os.path.join(ROOT_PATH, "portfolio", "active_voice.json")
    profile = VOICE_PROFILES[profile_id]
    
    # Resolve absolute path to reference audio
    ref_audio_rel = profile["reference_audio"]
    if profile_id == "default":
        # Sliced version path
        ref_audio_abs = os.path.abspath(os.path.join(ROOT_PATH, "voices", "reference_voice_sliced.wav"))
        if not os.path.exists(ref_audio_abs):
            ref_audio_abs = os.path.abspath(os.path.join(ROOT_PATH, ref_audio_rel))
    else:
        ref_audio_abs = os.path.abspath(os.path.join(ROOT_PATH, ref_audio_rel))
        
    cache_data = {
        "profile_id": profile_id,
        "voice_name": profile["voice_name"],
        "ref_audio_path": ref_audio_abs.replace("\\", "/"),
        "prompt_text": profile["prompt_text"],
        "tuning": profile["tuning"]
    }
    
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache_data, f, indent=2)
        print(f"Cache written to active_voice.json for profile '{profile_id}'")
        return True
    except Exception as e:
        print(f"Failed to write active_voice.json cache: {e}")
        return False

def save_active_profile_id(profile_id):
    if profile_id not in VOICE_PROFILES:
        return False
        
    # Trigger voice generation if needed
    if profile_id == "mature_calm":
        generate_mature_calm_ref_sync()
    elif profile_id == "default":
        generate_default_ref_sync()
        
    config_path = os.path.join(VOICES_DIR, "active_profile.json")
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump({"active_profile_id": profile_id}, f, indent=2)
        write_active_voice_cache(profile_id)
        return True
    except Exception as e:
        print(f"Failed to save active_profile.json: {e}")
        return False

def get_locked_profile():
    profile_id = get_active_profile_id()
    profile = VOICE_PROFILES[profile_id]
    
    return {
        "voice_name": profile["voice_name"],
        "speaker_id": profile_id,
        "reference_audio": profile["reference_audio"],
        "voice_locked": True
    }

def get_tuning():
    profile_id = get_active_profile_id()
    return dict(VOICE_PROFILES[profile_id]["tuning"])

def get_absolute_reference_path():
    ref_path = os.path.join(VOICES_DIR, "reference_voice.wav")
    if os.path.exists(ref_path):
        return os.path.abspath(ref_path)
    profile_id = get_active_profile_id()
    profile = VOICE_PROFILES.get(profile_id, VOICE_PROFILES["default"])
    return os.path.abspath(os.path.join(ROOT_PATH, profile["reference_audio"]))

# Initialize cache at import time
try:
    write_active_voice_cache(get_active_profile_id())
except Exception:
    pass
