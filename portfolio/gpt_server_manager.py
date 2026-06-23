import os
import sys
import subprocess
import time
import socket
import threading
import urllib.request
import json
import logging

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from voice_manager import get_absolute_reference_path

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CLONE_DIR = os.path.join(ROOT_DIR, "GPT-SoVITS")
PORT = 9880
STATUS_FILE = os.path.join(ROOT_DIR, "portfolio", "gpt_setup_status.json")
LOG_DIR = os.path.join(ROOT_DIR, "portfolio", "logs")
RECOVERY_LOG = os.path.join(LOG_DIR, "gpt_recovery.log")

# Setup logger for recovery
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO)
recovery_logger = logging.getLogger("GPTRecovery")
fh = logging.FileHandler(RECOVERY_LOG, encoding='utf-8')
fh.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
recovery_logger.addHandler(fh)

class GPTServerManager:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        with cls._lock:
            if not cls._instance:
                cls._instance = super(GPTServerManager, cls).__new__(cls, *args, **kwargs)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        self.process = None
        self.should_be_running = True
        self.server_status = "OFFLINE" # ONLINE, OFFLINE, STARTING, ERROR
        self.error_reason = "" # Missing Weights, Port 9880 Already In Use, Python Dependency Missing, GPU Not Available
        self.gpu_name = "N/A"
        self.vram_total = 0.0
        self.vram_used = 0.0
        self.vram_free = 0.0
        self.gpu_available = False
        
        self.last_crash_time = 0
        self.consecutive_crashes = 0
        
        # Load GPU info
        self.update_gpu_info()
        
        # Start background monitor thread
        self.monitor_thread = threading.Thread(target=self._monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()

    def update_gpu_info(self):
        # 1. Try nvidia-smi
        try:
            res = subprocess.run(
                ["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2.0, check=True
            )
            lines = res.stdout.strip().split("\n")
            if lines:
                parts = lines[0].split(",")
                self.gpu_name = parts[0].strip()
                self.vram_total = round(float(parts[1].strip()) / 1024.0, 2)
                self.vram_used = round(float(parts[2].strip()) / 1024.0, 2)
                self.vram_free = round(self.vram_total - self.vram_used, 2)
                self.gpu_available = True
                return
        except Exception:
            pass

        # 2. Try importing torch
        try:
            import torch
            if torch.cuda.is_available():
                self.gpu_name = torch.cuda.get_device_name(0)
                self.vram_total = round(torch.cuda.get_device_properties(0).total_memory / (1024**3), 2)
                self.vram_used = round(torch.cuda.memory_allocated(0) / (1024**3), 2)
                self.vram_free = round(self.vram_total - self.vram_used, 2)
                self.gpu_available = True
                return
        except Exception:
            pass

        self.gpu_name = "N/A (CPU Mode)"
        self.vram_total = 0.0
        self.vram_used = 0.0
        self.vram_free = 0.0
        self.gpu_available = False

    def is_port_in_use(self, port=PORT):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return False
            except OSError:
                return True

    def check_weights_exist(self):
        # Checks if repository is cloned and core weights are present
        if not os.path.exists(CLONE_DIR):
            return False
            
        required_weights = [
            "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
            "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s2G2333k.pth",
            "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s2D2333k.pth"
        ]
        for w in required_weights:
            path = os.path.join(CLONE_DIR, w)
            if not os.path.exists(path) or os.path.getsize(path) < 10000:
                return False
        return True

    def check_python_dependencies(self):
        try:
            import torch
            import fastapi
            import uvicorn
            import librosa
            import soundfile
            import scipy
            import yaml
            return True
        except ImportError:
            return False

    def verify_voice_synthesis(self):
        # Performs a lightweight test synthesis payload to verify the TTS model is functional
        payload = {
            "text": "Hello, I am Kazumi.",
            "text_lang": "en",
            "ref_audio_path": get_absolute_reference_path(),
            "prompt_text": "Are you trying to scare me or just being dramatic? Seriously, are you okay?",
            "prompt_lang": "en",
            "speed_factor": 1.0,
            "voice_lock": True
        }
        
        req_url = f"http://127.0.0.1:{PORT}/tts"
        req_data = json.dumps(payload).encode('utf-8')
        
        try:
            req = urllib.request.Request(
                req_url, data=req_data, 
                headers={'Content-Type': 'application/json'}, method="POST"
            )
            with urllib.request.urlopen(req, timeout=45.0) as response:
                audio_bytes = response.read()
                if audio_bytes and len(audio_bytes) > 1000:
                    # Valid output WAV bytes generated successfully
                    return True
        except Exception as e:
            recovery_logger.warning(f"Voice test synthesis failed verification: {e}")
        return False

    def _cleanup_process(self):
        if self.process:
            pid = self.process.pid
            recovery_logger.info(f"Terminating process tree for PID {pid}...")
            try:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, timeout=3.0)
            except Exception as e:
                recovery_logger.warning(f"taskkill failed: {e}. Falling back to standard termination.")
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2.0)
                except Exception:
                    try:
                        self.process.kill()
                    except Exception:
                        pass
            self.process = None

    def start_server(self):
        if self.process and self.process.poll() is None:
            if self.server_status in ["ONLINE", "STARTING"]:
                # Already running healthy
                return True
            else:
                # Running but unhealthy/error state, clean it up first
                recovery_logger.warning("Terminating unhealthy/stale server process before restart...")
                self._cleanup_process()

        self.server_status = "STARTING"
        self.error_reason = ""
        recovery_logger.info("Initiating server startup sequence...")

        # 1. Verify weights
        if not self.check_weights_exist():
            self.server_status = "ERROR"
            self.error_reason = "Missing Weights"
            recovery_logger.error("Startup aborted: Missing model weights.")
            return False

        # 2. Verify dependencies
        if not self.check_python_dependencies():
            self.server_status = "ERROR"
            self.error_reason = "Python Dependency Missing"
            recovery_logger.error("Startup aborted: Missing Python dependencies (PyTorch/Scipy/Librosa).")
            return False

        # 3. Verify port is not used
        if self.is_port_in_use(PORT):
            # Check if it's already responding as a GPT-SoVITS server
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{PORT}/", method="GET")
                with urllib.request.urlopen(req, timeout=1.0) as response:
                    # Port is responding, let's verify if we can do synthesis or check its health
                    recovery_logger.info("Port 9880 already occupied but responding. Performing voice verification...")
                    if self.verify_voice_synthesis():
                        self.server_status = "ONLINE"
                        return True
            except Exception:
                pass
                
            self.server_status = "ERROR"
            self.error_reason = "Port 9880 Already In Use"
            recovery_logger.error("Startup aborted: Port 9880 already in use by another process.")
            return False

        # 4. Attempt subprocess launch
        script_path = os.path.join(CLONE_DIR, "api_v2.py")
        if not os.path.exists(script_path):
            self.server_status = "ERROR"
            self.error_reason = "Missing Weights"
            recovery_logger.error("Startup aborted: api_v2.py launcher not found inside GPT-SoVITS directory.")
            return False

        # Build args to force CPU if CUDA not present, using unbuffered output
        args = [sys.executable, "-u", "api_v2.py", "-a", "127.0.0.1", "-p", str(PORT)]
        
        # Load GPU info
        self.update_gpu_info()
        
        server_log_file = os.path.join(LOG_DIR, "gpt_server.log")
        try:
            # Clear standard streams by writing directly to a file
            log_f = open(server_log_file, "w", encoding="utf-8")
            self.process = subprocess.Popen(
                args, cwd=CLONE_DIR,
                stdout=log_f, stderr=log_f,
                text=True
            )
            log_f.close()
            
            # Non-blocking wait for port to become active (up to 45 seconds)
            for _ in range(45):
                time.sleep(1.0)
                if self.process.poll() is not None:
                    # Exited immediately, check errors
                    stderr_txt = ""
                    try:
                        with open(server_log_file, "r", encoding="utf-8") as f:
                            stderr_txt = f.read()
                    except Exception:
                        pass
                    if "ModuleNotFoundError" in stderr_txt or "ImportError" in stderr_txt:
                        self.server_status = "ERROR"
                        self.error_reason = "Python Dependency Missing"
                    elif "cuda" in stderr_txt.lower() or "device" in stderr_txt.lower():
                        self.server_status = "ERROR"
                        self.error_reason = "GPU Not Available"
                    else:
                        self.server_status = "ERROR"
                        self.error_reason = "GPU Not Available" if not self.gpu_available else "Python Dependency Missing"
                    recovery_logger.error(f"Server crashed during launch: {stderr_txt}")
                    return False
                    
                if self.is_port_in_use(PORT):
                    # Port is alive, verify synthesis quality
                    recovery_logger.info("Server port online. Performing voice verification run...")
                    if self.verify_voice_synthesis():
                        self.server_status = "ONLINE"
                        recovery_logger.info("Voice verification successful. GPT-SoVITS server marked ONLINE.")
                        return True
                    else:
                        self.server_status = "ERROR"
                        self.error_reason = "GPU Not Available" if not self.gpu_available else "Python Dependency Missing"
                        return False
            
            self.server_status = "ERROR"
            self.error_reason = "GPU Not Available" if not self.gpu_available else "Python Dependency Missing"
            recovery_logger.error("Server took too long to bind to port 9880.")
            return False
            
        except Exception as e:
            self.server_status = "ERROR"
            self.error_reason = "Python Dependency Missing"
            recovery_logger.error(f"Unexpected launch failure: {e}")
            return False

    def stop_server(self):
        self.should_be_running = False
        if self.process:
            self._cleanup_process()
        self.server_status = "OFFLINE"
        recovery_logger.info("GPT-SoVITS server manually stopped.")

    def _monitor_loop(self):
        # Periodically runs health verification check every 5 seconds and handles auto recovery crashes
        while True:
            # Check setup completed first before launching monitor
            setup_status = {}
            if os.path.exists(STATUS_FILE):
                try:
                    with open(STATUS_FILE, "r", encoding="utf-8") as f:
                        setup_status = json.load(f)
                except Exception:
                    pass
            
            if setup_status.get("status") != "completed":
                # Downloader is not finished, skip auto launch
                self.server_status = "OFFLINE"
                self._write_manager_status()
                time.sleep(5.0)
                continue

            if not self.should_be_running:
                self._write_manager_status()
                time.sleep(5.0)
                continue

            # Update GPU telemetry info
            self.update_gpu_info()

            # Health Check Ping
            server_responding = False
            try:
                req = urllib.request.Request(f"http://127.0.0.1:{PORT}/", method="GET")
                with urllib.request.urlopen(req, timeout=1.5) as response:
                    server_responding = True
            except Exception as e:
                # If server responds with method not allowed or similar, it's alive
                if hasattr(e, 'code') or "HTTP" in str(e):
                    server_responding = True

            if server_responding:
                if self.server_status != "ONLINE":
                    # Double check via voice synthesis validation
                    if self.verify_voice_synthesis():
                        self.server_status = "ONLINE"
                        self.error_reason = ""
                    else:
                        self.server_status = "ERROR"
                        if not self.gpu_available:
                            self.error_reason = "GPU Not Available"
                        else:
                            self.error_reason = "Python Dependency Missing"
            else:
                # Server is unresponsive
                if self.server_status == "ONLINE":
                    # It was online but crashed!
                    recovery_logger.warning("Engine crash detected. Attempting recovery...")
                    print("[Auto Recovery] Engine crash detected. Attempting recovery...")
                    
                self.server_status = "OFFLINE"
                
                # Check if we should auto start
                if self.should_be_running:
                    success = self.start_server()
                    if success:
                        recovery_logger.info("Recovery successful. Server restarted and verified.")
                        print("[Auto Recovery] Recovery successful.")
                    else:
                        recovery_logger.error("Auto recovery failed. Server remains offline/error state.")
            
            self._write_manager_status()
            time.sleep(5.0)

    def _write_manager_status(self):
        manager_status_file = os.path.join(ROOT_DIR, "portfolio", "gpt_manager_status.json")
        try:
            with open(manager_status_file, "w", encoding="utf-8") as f:
                json.dump(self.get_status_dict(), f, indent=2)
        except Exception:
            pass

    def get_status_dict(self):
        self.update_gpu_info()
        ref_path = os.path.join(ROOT_DIR, "voices", "reference_voice.wav")
        ref_exists = os.path.exists(ref_path) and os.path.getsize(ref_path) > 1000
        
        # Read recovery logs
        recovery_logs = []
        if os.path.exists(RECOVERY_LOG):
            try:
                with open(RECOVERY_LOG, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    recovery_logs = [l.strip() for l in lines[-10:] if l.strip()]
            except Exception:
                pass
        if not recovery_logs:
            recovery_logs = ["[System] Lifecycle monitor initialized."]

        return {
            "serverOnline": self.server_status == "ONLINE",
            "serverStatus": self.server_status,
            "errorReason": self.error_reason,
            "gpuName": self.gpu_name,
            "vramTotal": self.vram_total,
            "vramUsed": self.vram_used,
            "vramFree": self.vram_free,
            "gpuAvailable": self.gpu_available,
            "voiceProfile": "Kazumi (Female Locked)",
            "referenceAudio": "reference_voice.wav",
            "referenceAudioStatus": "Loaded Successfully" if ref_exists else "Load Failed",
            "recoveryLogs": recovery_logs
        }
