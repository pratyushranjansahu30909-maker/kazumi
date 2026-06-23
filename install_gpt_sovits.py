import os
import sys
import subprocess
import urllib.request
import json
import threading

REPO_URL = "https://github.com/RVC-Boss/GPT-SoVITS.git"
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
CLONE_DIR = os.path.join(ROOT_DIR, "GPT-SoVITS")
STATUS_FILE = os.path.join(ROOT_DIR, "portfolio", "gpt_setup_status.json")

# Pretrained models map
DOWNLOAD_MAP = {
    "s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt": {
        "url": "https://huggingface.co/lj1995/GPT-SoVITS/resolve/main/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt",
        "dest": "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt"
    },
    "s2G2333k.pth": {
        "url": "https://huggingface.co/lj1995/GPT-SoVITS/resolve/main/gsv-v2final-pretrained/s2G2333k.pth",
        "dest": "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s2G2333k.pth"
    },
    "s2D2333k.pth": {
        "url": "https://huggingface.co/lj1995/GPT-SoVITS/resolve/main/gsv-v2final-pretrained/s2D2333k.pth",
        "dest": "GPT_SoVITS/pretrained_models/gsv-v2final-pretrained/s2D2333k.pth"
    },
    "roberta_config.json": {
        "url": "https://huggingface.co/lj1995/GPT-SoVITS/resolve/main/chinese-roberta-wwm-ext-large/config.json",
        "dest": "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext/config.json"
    },
    "roberta_pytorch_model.bin": {
        "url": "https://huggingface.co/lj1995/GPT-SoVITS/resolve/main/chinese-roberta-wwm-ext-large/pytorch_model.bin",
        "dest": "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext/pytorch_model.bin"
    },
    "roberta_vocab.txt": {
        "url": "https://huggingface.co/hfl/chinese-roberta-wwm-ext-large/resolve/main/vocab.txt",
        "dest": "GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext/vocab.txt"
    },
    "hubert_pytorch_model.bin": {
        "url": "https://huggingface.co/lj1995/GPT-SoVITS/resolve/main/chinese-hubert-base/pytorch_model.bin",
        "dest": "GPT_SoVITS/pretrained_models/chinese-hubert-base/pytorch_model.bin"
    }
}

ESTIMATED_TOTAL_BYTES = 2200000000  # ~2.2 GB
downloaded_bytes_global = 0

def get_gpu_info_local():
    try:
        res = subprocess.run(["nvidia-smi", "--query-gpu=name,memory.total,memory.used", "--format=csv,noheader,nounits"], capture_output=True, text=True, check=True)
        lines = res.stdout.strip().split("\n")
        if lines:
            parts = lines[0].split(",")
            return True, parts[0].strip()
    except Exception:
        pass
    return False, "N/A"

def update_status(status, progress=0, message="", downloaded_size="0 GB / 2.2 GB", error=None):
    data = {
        "status": status,
        "progress": progress,
        "message": message,
        "downloadedSize": downloaded_size,
        "error": error
    }
    try:
        os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Failed to write status: {e}")

def check_dependencies():
    missing = []
    dependencies = ["torch", "uvicorn", "fastapi", "librosa", "soundfile", "scipy", "yaml"]
    for dep in dependencies:
        try:
            if dep == "yaml":
                import yaml
            else:
                __import__(dep)
        except ImportError:
            missing.append(dep)
    return missing

def install_dependencies():
    missing = check_dependencies()
    if not missing:
        print("All dependencies present.")
        return True
        
    print(f"Installing missing dependencies: {missing}")
    update_status("running", 2, f"Installing dependencies: {', '.join(missing)}...")
    
    # Check GPU
    gpu_available, _ = get_gpu_info_local()
    
    if "torch" in missing:
        try:
            if gpu_available:
                print("NVIDIA GPU detected. Installing CUDA PyTorch...")
                subprocess.run([sys.executable, "-m", "pip", "install", "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu118"], check=True)
            else:
                print("No GPU detected. Installing CPU PyTorch...")
                subprocess.run([sys.executable, "-m", "pip", "install", "torch", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cpu"], check=True)
            missing.remove("torch")
        except Exception as e:
            update_status("failed", 0, "PyTorch installation failed", error=f"Python Dependency Missing: {str(e)}")
            return False
            
    # Install others
    for dep in missing:
        pkg_name = "pyyaml" if dep == "yaml" else dep
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg_name], check=True)
        except Exception as e:
            update_status("failed", 0, f"{dep} installation failed", error=f"Python Dependency Missing: {str(e)}")
            return False
            
    return True

def download_file(url, dest_path, filename):
    global downloaded_bytes_global
    print(f"Downloading {filename}...")
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    
    try:
        with urllib.request.urlopen(req) as response:
            total_size = int(response.info().get('Content-Length', 0))
            downloaded = 0
            block_size = 1024 * 1024  # 1MB
            
            with open(dest_path, "wb") as f:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    f.write(buffer)
                    downloaded += len(buffer)
                    downloaded_bytes_global += len(buffer)
                    
                    # Yield current file progress
                    if total_size > 0:
                        file_progress = int((downloaded / total_size) * 100)
                        yield file_progress
    except Exception as e:
        raise RuntimeError(f"Error downloading {filename}: {str(e)}")

def run_setup():
    global downloaded_bytes_global
    
    # 1. Check & Install dependencies
    if not install_dependencies():
        return
        
    # 2. Clone repository
    update_status("running", 5, "Cloning GPT-SoVITS repository...")
    if not os.path.exists(CLONE_DIR):
        try:
            print("Cloning repository...")
            subprocess.run(["git", "clone", REPO_URL, CLONE_DIR], check=True)
        except Exception as e:
            update_status("failed", 0, "Git clone failed", error=f"Git clone error: {str(e)}")
            return
    else:
        print("GPT-SoVITS folder already exists. Skipping clone.")

    # Create config directory if not exists
    os.makedirs(os.path.join(CLONE_DIR, "GPT_SoVITS", "configs"), exist_ok=True)

    # 3. Download weights
    update_status("running", 10, "Starting weights download...", "0 GB / 2.2 GB")
    
    total_files = len(DOWNLOAD_MAP)
    completed_files = 0
    
    for filename, info in DOWNLOAD_MAP.items():
        dest_abs = os.path.join(CLONE_DIR, info["dest"])
        # If file exists and is of appropriate size, skip it and add to global count
        min_size = 200 if "config.json" in filename else 10000
        if os.path.exists(dest_abs) and os.path.getsize(dest_abs) > min_size:
            file_size = os.path.getsize(dest_abs)
            downloaded_bytes_global += file_size
            completed_files += 1
            continue
            
        try:
            for file_progress in download_file(info["url"], dest_abs, filename):
                # Calculate display strings
                dl_gb = round(downloaded_bytes_global / (1024**3), 2)
                tot_gb = round(ESTIMATED_TOTAL_BYTES / (1024**3), 2)
                dl_str = f"{dl_gb} GB / {tot_gb} GB"
                
                # Overall progress scale from 10% to 95%
                base_progress = 10 + int((completed_files / total_files) * 85)
                current_file_share = int((file_progress / 100) * (85 / total_files))
                total_progress = min(95, base_progress + current_file_share)
                
                update_status("running", total_progress, f"Downloading {filename}: {file_progress}%", dl_str)
            completed_files += 1
        except Exception as e:
            update_status("failed", 0, f"Download failed on {filename}", error=f"Missing Weights: {str(e)}")
            return

    # 4. Validation Check
    update_status("running", 96, "Validating pretrained models folder...", f"{round(ESTIMATED_TOTAL_BYTES / (1024**3), 2)} GB / {round(ESTIMATED_TOTAL_BYTES / (1024**3), 2)} GB")
    missing_models = []
    for filename, info in DOWNLOAD_MAP.items():
        dest_abs = os.path.join(CLONE_DIR, info["dest"])
        min_size = 200 if "config.json" in filename else 10000
        if not os.path.exists(dest_abs) or os.path.getsize(dest_abs) < min_size:
            missing_models.append(filename)
            
    if missing_models:
        print(f"Validation failed. Missing files: {missing_models}")
        update_status("failed", 0, "Validation failed: missing weights", error=f"Missing Weights: Files {missing_models} missing or corrupted.")
        return

    # 5. Complete
    dl_gb_tot = round(ESTIMATED_TOTAL_BYTES / (1024**3), 2)
    update_status("completed", 100, "Setup complete! GPT-SoVITS successfully installed.", f"{dl_gb_tot} GB / {dl_gb_tot} GB")
    print("Setup completed successfully!")

def start_setup_thread():
    t = threading.Thread(target=run_setup)
    t.daemon = True
    t.start()
    return t

if __name__ == "__main__":
    run_setup()
