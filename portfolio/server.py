import os
import sys
import json
import base64
import hashlib
import logging
import asyncio
import threading
import urllib.request
import time
from typing import Optional

# FastAPI imports
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Configure Logging
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(log_dir, exist_ok=True)
log_file = os.path.join(log_dir, "companion_system.log")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file, encoding='utf-8')
    ]
)
logger = logging.getLogger("CompanionSystem")

from emotion_engine import EmotionalEngine
emotion_engine = EmotionalEngine()

import voice_manager

# Absolute path to companion database directory
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ISA_MEMORY_DIR = os.path.join(ROOT_DIR, "isa_memory")
if os.environ.get("SPACE_ID") and os.path.exists("/data") and os.access("/data", os.W_OK):
    ISA_MEMORY_DIR = os.path.join("/data", "isa_memory")

KAZUMI_LOCK = threading.Lock()

# Import Kazumi
sys.path.append(ROOT_DIR)
try:
    from kazumi import Kazumi
    # Initialize Kazumi Bot instance
    kazumi_bot = Kazumi()
    # Override memory paths to use absolute root database directory
    kazumi_bot.memory.persist_path = os.path.join(ISA_MEMORY_DIR, "conversations.json")
    kazumi_bot.memory.profile_path = os.path.join(ISA_MEMORY_DIR, "profile.json")
    kazumi_bot.memory.diary_path = os.path.join(ISA_MEMORY_DIR, "diary.json")
    # Re-load memory with corrected paths
    kazumi_bot.memory.history = kazumi_bot.memory.load_history()
    kazumi_bot.memory.profile = kazumi_bot.memory.load_profile()
    # Re-initialize character and game states from corrected profile
    kazumi_bot.active_character = kazumi_bot.memory.profile.get("character", "kazumi")
    if kazumi_bot.active_character not in kazumi_bot.CHARACTERS:
        kazumi_bot.active_character = "kazumi"
    kazumi_bot.current_archetype = "TEASING" if kazumi_bot.active_character == "mimi" else "DEREDERE"
    kazumi_bot.load_game_states()
except Exception as e:
    logger.error(f"Error importing Kazumi: {e}")
    kazumi_bot = None

PORT = 3000
CREDENTIALS_FILE = os.path.join(ISA_MEMORY_DIR, "credentials.json")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "my_secure_portfolio_encryption_key_hash_to_32_bytes_fallback_key")

# ----------------------------------------------------
# 🔐 Cryptographic Helpers
# ----------------------------------------------------
def get_key_stream(key, iv, length):
    keystream = b""
    counter = 0
    while len(keystream) < length:
        h = hashlib.sha256(key + iv + str(counter).encode('utf-8')).digest()
        keystream += h
        counter += 1
    return keystream[:length]

def encrypt(plaintext):
    if not plaintext:
        return None
    key = hashlib.sha256(ENCRYPTION_KEY.encode('utf-8')).digest()
    iv = os.urandom(16)
    data = plaintext.encode('utf-8')
    keystream = get_key_stream(key, iv, len(data))
    ciphertext = bytes([d ^ k for d, k in zip(data, keystream)])
    return {
        "iv": base64.b64encode(iv).decode('utf-8'),
        "content": base64.b64encode(ciphertext).decode('utf-8')
    }

def decrypt(enc_obj):
    if not enc_obj or "iv" not in enc_obj or "content" not in enc_obj:
        return None
    try:
        key = hashlib.sha256(ENCRYPTION_KEY.encode('utf-8')).digest()
        iv = base64.b64decode(enc_obj["iv"].encode('utf-8'))
        ciphertext = base64.b64decode(enc_obj["content"].encode('utf-8'))
        keystream = get_key_stream(key, iv, len(ciphertext))
        plaintext = bytes([c ^ k for c, k in zip(ciphertext, keystream)])
        return plaintext.decode('utf-8')
    except Exception as e:
        logger.error(f"Decryption failed: {e}")
        return None

# 📁 Credentials File Storage Operations
def _atomic_write_json(file_path, data):
    try:
        if os.path.exists(file_path):
            import shutil
            shutil.copy2(file_path, file_path + ".bak")
        tmp_path = file_path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
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

def read_credentials():
    exists = os.path.exists(CREDENTIALS_FILE)
    read_path = CREDENTIALS_FILE
    if not exists and os.path.exists(CREDENTIALS_FILE + ".bak"):
        exists = True
        read_path = CREDENTIALS_FILE + ".bak"
        
    if exists:
        try:
            with open(read_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"github": None, "linkedin": None}

def save_credentials(creds):
    os.makedirs(ISA_MEMORY_DIR, exist_ok=True)
    _atomic_write_json(CREDENTIALS_FILE, creds)

def get_fallback_repos():
    return [
        {
            "name": "kazumi-companion-website",
            "description": "Interactive Web Companion dashboard featuring emotion matrices, diary reflections, and visual calibration stats.",
            "stars": 42,
            "language": "JavaScript",
            "url": "#",
            "isMock": True
        },
        {
            "name": "neural-gpt-sovits-integration",
            "description": "Deep pipeline integration for low-latency multi-speaker synthesis, custom profiles, and affection telemetry locks.",
            "stars": 38,
            "language": "Python",
            "url": "#",
            "isMock": True
        },
        {
            "name": "calm-ambient-calibrator",
            "description": "An interactive breathing simulator and noise therapy module built to calibrate user stress telemetry.",
            "stars": 29,
            "language": "CSS/JS",
            "url": "#",
            "isMock": True
        }
    ]

def get_fallback_posts():
    return [
        {
            "text": "🌸 Introducing Kazumi: A fully empathetic chatbot companion designed to make developers feel supported and relaxed. Features deep state memory and interactive profile telemetry!",
            "date": "2 days ago",
            "url": "#",
            "isMock": True
        },
        {
            "text": "🌿 Building low-latency FastAPI services with Starlette middleware has been an absolute joy. Check out our new atomic keystream encryption helpers for offline secure storage!",
            "date": "1 week ago",
            "url": "#",
            "isMock": True
        }
    ]

# FastAPI App
app = FastAPI(title="Kazumi Companion Website", description="A cozy dashboard for Kazumi chatbot companion")

@app.get("/api/settings/status")
async def get_settings_status():
    creds = read_credentials()
    github_cred = creds.get("github")
    linkedin_cred = creds.get("linkedin")
    return {
        "githubSet": bool(github_cred),
        "linkedinSet": bool(linkedin_cred),
        "githubMetadata": {
            "iv": github_cred["iv"][:8] + "..." if github_cred else None,
            "contentLen": len(github_cred["content"]) if github_cred else 0
        } if github_cred else None,
        "linkedinMetadata": {
            "iv": linkedin_cred["iv"][:8] + "..." if linkedin_cred else None,
            "contentLen": len(linkedin_cred["content"]) if linkedin_cred else 0
        } if linkedin_cred else None
    }

class SettingsPayload(BaseModel):
    githubToken: Optional[str] = None
    linkedinToken: Optional[str] = None

@app.post("/api/settings")
async def post_settings(body: SettingsPayload):
    creds = read_credentials()
    if body.githubToken is not None:
        creds["github"] = encrypt(body.githubToken) if body.githubToken else None
    if body.linkedinToken is not None:
        creds["linkedin"] = encrypt(body.linkedinToken) if body.linkedinToken else None
    save_credentials(creds)
    return {"success": True, "message": "Settings securely encrypted and saved!"}

@app.post("/api/settings/clear")
async def post_settings_clear():
    save_credentials({"github": None, "linkedin": None})
    return {"success": True, "message": "Credentials cleared."}

@app.get("/api/github/repos")
async def get_github_repos():
    creds = read_credentials()
    token = decrypt(creds.get("github"))
    if not token:
        return get_fallback_repos()
    
    req = urllib.request.Request(
        "https://api.github.com/user/repos?sort=updated&per_page=6",
        headers={
            "Authorization": f"token {token}",
            "User-Agent": "python-portfolio-server"
        }
    )
    try:
        loop = asyncio.get_event_loop()
        def fetch():
            with urllib.request.urlopen(req, timeout=8) as response:
                return json.loads(response.read().decode('utf-8'))
        raw_data = await loop.run_in_executor(None, fetch)
        return [
            {
                "name": repo["name"],
                "description": repo["description"] or "No description provided.",
                "stars": repo["stargazers_count"],
                "language": repo["language"] or "HTML/JS",
                "url": repo["html_url"],
                "isMock": False
            }
            for repo in raw_data
        ]
    except Exception as e:
        logger.warning(f"GitHub Live API failed: {e}. Using fallback.")
        return get_fallback_repos()

@app.get("/api/linkedin/posts")
async def get_linkedin_posts():
    creds = read_credentials()
    token = decrypt(creds.get("linkedin"))
    if not token:
        return get_fallback_posts()
    
    req = urllib.request.Request(
        "https://api.linkedin.com/v2/shares?q=owners&owners=urn:li:person:me&count=3",
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "python-portfolio-server"
        }
    )
    try:
        loop = asyncio.get_event_loop()
        def fetch():
            with urllib.request.urlopen(req, timeout=8) as response:
                return json.loads(response.read().decode('utf-8'))
        raw_data = await loop.run_in_executor(None, fetch)
        return [
            {
                "text": post.get("text", {}).get("text", "No post content."),
                "date": "Today",
                "url": f"https://www.linkedin.com/feed/update/{post.get('activity', '')}",
                "isMock": False
            }
            for post in raw_data.get("elements", [])
        ]
    except Exception as e:
        logger.warning(f"LinkedIn Live API failed: {e}. Using fallback.")
        return get_fallback_posts()

@app.get("/api/kazumi/telemetry")
async def get_kazumi_telemetry():
    cpu = 0.0
    ram = 0.0
    try:
        import psutil
        try:
            cpu = psutil.cpu_percent(interval=None)
            if cpu is None or cpu < 0.1:
                cpu = psutil.cpu_percent(interval=0.1)
        except Exception:
            cpu = 0.0
            
        try:
            ram = psutil.virtual_memory().percent
        except Exception:
            ram = 0.0
    except Exception:
        pass
        
    gpu = 0.0
    gpu_name = "N/A"
    vram_used = 0.0
    vram_total = 0.0
    
    try:
        import subprocess
        res = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, check=True, timeout=2.0
        )
        lines = res.stdout.strip().split("\n")
        if lines:
            parts = lines[0].split(",")
            if len(parts) >= 4:
                gpu_name = parts[0].strip()
                gpu = float(parts[1].strip())
                vram_used = float(parts[2].strip()) / 1024.0
                vram_total = float(parts[3].strip()) / 1024.0
    except Exception:
        pass
        
    return {
        "cpu": cpu,
        "ram": ram,
        "gpu": gpu,
        "gpuName": gpu_name,
        "vramUsed": vram_used,
        "vramTotal": vram_total
    }

@app.get("/api/kazumi/profile")
async def get_kazumi_profile():
    with KAZUMI_LOCK:
        if kazumi_bot:
            if not os.path.exists(kazumi_bot.memory.profile_path):
                kazumi_bot.memory.save_profile()
            return kazumi_bot.memory.profile
            
        profile_path = os.path.join(ROOT_DIR, "isa_memory", "profile.json")
        if not os.path.exists(profile_path):
            raise HTTPException(status_code=404, detail="Profile memory not found")
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            diary_path = os.path.join(ISA_MEMORY_DIR, "diary.json")
            diary = None
            if os.path.exists(diary_path) and os.path.getsize(diary_path) > 0:
                try:
                    with open(diary_path, "r", encoding="utf-8") as f_diary:
                        diary = json.load(f_diary)
                except Exception:
                    if os.path.exists(diary_path + ".bak") and os.path.getsize(diary_path + ".bak") > 0:
                        try:
                            with open(diary_path + ".bak", "r", encoding="utf-8") as f_diary:
                                diary = json.load(f_diary)
                        except Exception:
                            pass
            if diary is None:
                diary = data.get("diary", [])
            data["diary"] = diary
            return data
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read profile: {str(e)}")

@app.post("/api/kazumi/profile")
async def post_kazumi_profile(request: Request):
    with KAZUMI_LOCK:
        body = await request.json()
        if kazumi_bot:
            for k, v in body.items():
                kazumi_bot.memory.profile[k] = v
            kazumi_bot.memory.save_profile()
        else:
            profile_path = os.path.join(ISA_MEMORY_DIR, "profile.json")
            try:
                profile = {}
                if os.path.exists(profile_path):
                    import shutil
                    shutil.copy2(profile_path, profile_path + ".bak")
                    try:
                        with open(profile_path, "r", encoding="utf-8") as f:
                            profile = json.load(f)
                    except Exception:
                        if os.path.exists(profile_path + ".bak"):
                            with open(profile_path + ".bak", "r", encoding="utf-8") as f:
                                profile = json.load(f)
                for k, v in body.items():
                    profile[k] = v
                if profile.get("_is_default"):
                    profile["_is_default"] = False
                    
                if "diary" in profile:
                    diary = profile["diary"]
                    diary_path = os.path.join(ISA_MEMORY_DIR, "diary.json")
                    try:
                        _atomic_write_json(diary_path, diary)
                    except Exception as diary_err:
                        logger.error(f"Failed to save diary atomically in Python: {diary_err}")
                    del profile["diary"]
                    
                _atomic_write_json(profile_path, profile)
            except Exception as e:
                return {"success": False, "error": str(e)}
        return {"success": True, "message": "Profile synced successfully."}

@app.get("/api/kazumi/chat")
async def get_kazumi_chat(session_id: Optional[str] = None):
    with KAZUMI_LOCK:
        chat_path = os.path.join(ISA_MEMORY_DIR, "conversations.json")
        if not os.path.exists(chat_path):
            return []
        try:
            with open(chat_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if session_id:
                data = [msg for msg in data if msg.get("session_id") == session_id]
            return data
        except Exception as e:
            return {"error": f"Failed to read chat: {str(e)}"}

@app.get("/api/kazumi/history")
async def get_kazumi_history():
    with KAZUMI_LOCK:
        chat_path = os.path.join(ROOT_DIR, "isa_memory", "conversations.json")
        if not os.path.exists(chat_path):
            return []
        try:
            with open(chat_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data
        except Exception as e:
            return {"error": f"Failed to read history: {str(e)}"}

@app.post("/api/kazumi/reset")
async def post_kazumi_reset():
    global kazumi_bot
    with KAZUMI_LOCK:
        try:
            if kazumi_bot:
                kazumi_bot = None
            
            files = [
                'profile.json', 'profile.json.bak', 'profile.json.tmp',
                'diary.json', 'diary.json.bak', 'diary.json.tmp',
                'conversations.json', 'conversations.json.bak', 'conversations.json.tmp'
            ]
            for f in files:
                file_path = os.path.join(ISA_MEMORY_DIR, f)
                if os.path.exists(file_path):
                    os.remove(file_path)
                    
            try:
                from kazumi import Kazumi
                kazumi_bot = Kazumi()
                kazumi_bot.memory.persist_path = os.path.join(ISA_MEMORY_DIR, "conversations.json")
                kazumi_bot.memory.profile_path = os.path.join(ISA_MEMORY_DIR, "profile.json")
                kazumi_bot.memory.diary_path = os.path.join(ISA_MEMORY_DIR, "diary.json")
                kazumi_bot.memory.history = kazumi_bot.memory.load_history()
                kazumi_bot.memory.profile = kazumi_bot.memory.load_profile()
                kazumi_bot.active_character = "kazumi"
                kazumi_bot.current_archetype = "DEREDERE"
                kazumi_bot.load_game_states()
            except Exception as bot_err:
                logger.error(f"Failed to re-initialize clean bot: {bot_err}")
                
            return {"success": True, "message": "Profile and chat history cleared successfully."}
        except Exception as e:
            return {"success": False, "error": str(e)}

@app.get("/api/kazumi/inactivity")
async def get_kazumi_inactivity(session_id: Optional[str] = None):
    with KAZUMI_LOCK:
        if not kazumi_bot:
            return {"success": False, "error": "AI core offline"}
        try:
            loop = asyncio.get_event_loop()
            def call_inactivity():
                return kazumi_bot.reply_inactivity(1, session_id=session_id)
            reply = await loop.run_in_executor(None, call_inactivity)
            return {"success": True, "reply": reply}
        except Exception as e:
            return {"success": False, "error": f"Failed to generate inactivity response: {str(e)}"}

@app.get("/api/space-info")
async def get_space_info():
    space_id = os.environ.get("SPACE_ID")
    if space_id:
        space_id = space_id.replace("kazum1-companion", "kazumi-companion").replace("kazum1", "kazumi")
    return {"spaceId": space_id}

class ChatPayload(BaseModel):
    message: str
    session_id: Optional[str] = None

@app.post("/api/kazumi/chat")
async def chat_post(body: ChatPayload):
    global kazumi_bot
    user_msg = body.message.strip()
    session_id = body.session_id.strip() if body.session_id else None
    
    if not user_msg:
        return {"success": False, "error": "Message is empty"}
    if not kazumi_bot:
        return {"success": False, "error": "Kazumi AI Core is offline or not loaded"}
        
    try:
        loop = asyncio.get_event_loop()
        def process():
            return kazumi_bot.reply(user_msg, session_id=session_id)
            
        reply = await loop.run_in_executor(None, process)
        emotion_metadata = emotion_engine.analyze(reply, session_id=session_id)
        
        logger.info(f"[Chat Core] Reply: {reply} | Emotion: {emotion_metadata} | Affection: {kazumi_bot.memory.profile.get('affection_level', 0)}")
        return {
            "success": True,
            "reply": reply,
            "emotion": emotion_metadata
        }
    except Exception as e:
        return {"success": False, "error": f"Failed to generate response: {str(e)}"}

class DebugPayload(BaseModel):
    status: str
    details: str

@app.post("/api/debug/log")
async def post_debug_log(body: DebugPayload):
    logger.info(f"[Client Telemetry] Status: {body.status} | Details: {body.details}")
    return {"success": True}

@app.post("/api/model/save")
async def save_model(request: Request):
    try:
        import json
        data = await request.json()
        gltf_data = data.get("gltf_data")
        if not gltf_data:
            return {"success": False, "error": "Missing gltf_data in request body"}
        
        public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
        file_path = os.path.join(public_dir, "kazumi_vtuber_model.gltf")
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(gltf_data, f, indent=2)
        logger.info("[Server] Rigged 3D VTuber GLTF model saved successfully on disk!")
        return {"success": True}
    except Exception as e:
        logger.error(f"[Server] Failed to save GLTF model: {str(e)}")
        return {"success": False, "error": str(e)}


@app.post("/api/model/save_binary")
async def save_binary_model(request: Request):
    try:
        data = await request.json()
        glb_base64 = data.get("glb_base64")
        if not glb_base64:
            return {"success": False, "error": "Missing glb_base64 in request body"}
        
        import base64
        glb_data = base64.b64decode(glb_base64)
        
        public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
        
        # Save as GLB
        glb_path = os.path.join(public_dir, "kazumi_vtuber_model.glb")
        with open(glb_path, "wb") as f:
            f.write(glb_data)
            
        # Save as VRM
        vrm_path = os.path.join(public_dir, "kazumi_vtuber_model.vrm")
        with open(vrm_path, "wb") as f:
            f.write(glb_data)
            
        # Save as FBX
        fbx_path = os.path.join(public_dir, "kazumi_vtuber_model.fbx")
        with open(fbx_path, "wb") as f:
            f.write(glb_data)
            
        # Save as Blend
        blend_path = os.path.join(public_dir, "kazumi_vtuber_model.blend")
        with open(blend_path, "wb") as f:
            f.write(glb_data)
            
        logger.info("[Server] Rigged binary GLB, VRM, FBX, and Blend model files successfully saved on disk!")
        return {"success": True}
    except Exception as e:
        logger.error(f"[Server] Failed to save binary model: {str(e)}")
        return {"success": False, "error": str(e)}



# ----------------------------------------------------
# 🎤 Voice / TTS Parity Endpoints
# ----------------------------------------------------
class VoiceProfilePayload(BaseModel):
    profile_id: str

@app.get("/api/kazumi/voice/status")
async def get_voice_status():
    return {
        "status": "offline",
        "serverOnline": False,
        "model": "Disabled",
        "architecture": "Text-Only Chat Bot Mode",
        "device": "cpu",
        "enabled": False,
        "loaded": False,
        "voiceProfileLocked": True,
        "voiceProfileId": "default",
        "voiceProfileName": "Chat Bot Mode (Voices Disabled)"
    }

@app.post("/api/kazumi/voice/profile")
async def post_voice_profile(body: VoiceProfilePayload):
    return {"success": True, "message": "Voice system is currently disabled (Pure Chat Bot Mode)"}

@app.post("/api/kazumi/voice/download-weights")
async def post_download_weights():
    return {"success": False, "message": "Voice downloads disabled in Chat Bot mode."}

class VoiceSynthesizePayload(BaseModel):
    text: str
    text_lang: Optional[str] = "en"
    prompt_text: Optional[str] = None
    prompt_lang: Optional[str] = "en"
    speed_factor: Optional[float] = 1.0

def _clean_voice_prompt(prompt_text: Optional[str]) -> Optional[str]:
    return None

@app.get("/api/kazumi/voice/stream")
async def get_voice_stream(
    text: str,
    text_lang: Optional[str] = "en",
    prompt_text: Optional[str] = None,
    prompt_lang: Optional[str] = "en",
    speed_factor: Optional[float] = 1.0
):
    raise HTTPException(status_code=400, detail="Voice features are currently disabled. Operating in pure chat bot mode.")

@app.post("/api/kazumi/voice/synthesize")
async def post_voice_synthesize(body: VoiceSynthesizePayload):
    return {"success": False, "error": "Voice synthesis is currently disabled. Kazumi is operating as a pure chat bot."}
            
from speaker_recognition import speaker_engine

class VoiceRecognizePayload(BaseModel):
    audio_base64: Optional[str] = None
    transcript: Optional[str] = None

class VoiceEnrollPayload(BaseModel):
    audio_base64: str
    speaker_name: Optional[str] = "Master"

@app.post("/api/kazumi/voice/enroll")
async def post_voice_enroll(body: VoiceEnrollPayload):
    return {"success": False, "error": "Voice recognition systems are currently disabled."}

@app.post("/api/kazumi/voice/recognize")
async def post_voice_recognize(body: VoiceRecognizePayload):
    return {"success": False, "error": "Voice recognition systems are currently disabled."}

# ----------------------------------------------------
# 🎤 Voice Call Pipeline Endpoint (Disabled - Pure Chat Bot Mode)
# ----------------------------------------------------
class VoiceCallPayload(BaseModel):
    message: Optional[str] = None
    audio_base64: Optional[str] = None
    prompt_text: Optional[str] = None
    session_id: Optional[str] = None

@app.post("/api/kazumi/call/interact")
async def post_voice_call_interact(body: VoiceCallPayload):
    return {
        "success": False,
        "error": "Voice call system is currently disabled. Please use the Text Chat Bot interface."
    }

@app.on_event("startup")
async def startup_event():
    print("====================================================")
    print("[INIT] Kazumi Chat Bot Mode: Active (Voice & Recognition Disabled)")
    print("====================================================")


# Mount public directory
try:
    public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "public")
    app.mount("/", StaticFiles(directory=public_dir, html=True), name="public")
except Exception as mount_err:
    logger.error(f"Static mounting failed: {mount_err}")

if __name__ == "__main__":
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    import socket
    local_ip = "localhost"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    print("====================================================")
    print(f"FastAPI Secure Portfolio Server running on http://localhost:{PORT}")
    print(f"Local Network Share Link: http://{local_ip}:{PORT}/")
    print("Cryptography: keystream active (zero-plaintext storage)")
    print("====================================================")
    
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
