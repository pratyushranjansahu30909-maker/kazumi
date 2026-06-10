import os
import json
import base64
import hashlib
import urllib.request
import urllib.error
from http.server import BaseHTTPRequestHandler, HTTPServer, ThreadingHTTPServer
import socketserver
import sys
from urllib.parse import urlparse, parse_qs
import threading

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
    # Re-load memory with corrected paths
    kazumi_bot.memory.history = kazumi_bot.memory.load_history()
    kazumi_bot.memory.profile = kazumi_bot.memory.load_profile()
except Exception as e:
    print(f"Error importing Kazumi: {e}")
    kazumi_bot = None

PORT = 3000
CREDENTIALS_FILE = os.path.join(ISA_MEMORY_DIR, "credentials.json")
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "my_secure_portfolio_encryption_key_hash_to_32_bytes_fallback_key")

# ----------------------------------------------------
# 🔐 Cryptographic Helpers (SHA-256 Keystream Cipher)
# ----------------------------------------------------

def get_key_stream(key, iv, length):
    """
    Generates a cryptographically secure keystream by chaining SHA-256 hashes
    of the key, IV, and a counter.
    """
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
    
    # XOR plaintext bytes with keystream bytes
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
        print("Decryption failed:", e)
        return None

# ----------------------------------------------------
# 📁 Credentials File Storage Operations
# ----------------------------------------------------

def read_credentials():
    exists = os.path.exists(CREDENTIALS_FILE)
    read_path = CREDENTIALS_FILE
    if not exists and os.path.exists(CREDENTIALS_FILE + ".bak"):
        exists = True
        read_path = CREDENTIALS_FILE + ".bak"
    if not exists:
        return {"github": None, "linkedin": None}
    try:
        with open(read_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        if read_path == CREDENTIALS_FILE and os.path.exists(CREDENTIALS_FILE + ".bak"):
            try:
                with open(CREDENTIALS_FILE + ".bak", "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {"github": None, "linkedin": None}

def save_credentials(creds):
    try:
        if os.path.exists(CREDENTIALS_FILE):
            import shutil
            shutil.copy2(CREDENTIALS_FILE, CREDENTIALS_FILE + ".bak")
        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump(creds, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("Failed to save credentials:", e)

# ----------------------------------------------------
# 🪐 Mock Fallback Data (Matching Node Server)
# ----------------------------------------------------

def get_fallback_repos():
    return [
        {
            "name": "kazumi-ai-companion",
            "description": "A sweet, highly empathetic conversational AI assistant running on Windows console with persistent JSON semantic memory, custom zodiac horoscopes, and multi-archetype support.",
            "stars": 128,
            "language": "Python",
            "url": "https://github.com",
            "isMock": True
        },
        {
            "name": "secure-vault-aes256",
            "description": "A Node.js & Electron dashboard for encrypting sensitive developer keys and configurations locally using secure AES-256-CBC cryptographic tunnels.",
            "stars": 84,
            "language": "JavaScript",
            "url": "https://github.com",
            "isMock": True
        },
        {
            "name": "starlight-tarot-engine",
            "description": "An interactive React-based digital tarot deck projecting stardust chimes and providing daily alignment horoscopes by pulling from cosmic JSON maps.",
            "stars": 52,
            "language": "TypeScript",
            "url": "https://github.com",
            "isMock": True
        },
        {
            "name": "quantum-key-distributor",
            "description": "A simulation of secure cryptographic key exchange using C++ and visual graph layers to demonstrate quantum cryptography principles.",
            "stars": 42,
            "language": "C++",
            "url": "https://github.com",
            "isMock": True
        }
    ]

def get_fallback_posts():
    return [
        {
            "text": "🚀 Excited to share my latest open-source project! I built a local secure vault using Node's crypto API to encrypt developer credentials on the fly. Security should always be a first-class citizen in full-stack applications. Check it out and let me know your thoughts!",
            "date": "Jun 3, 2026",
            "url": "https://linkedin.com",
            "isMock": True
        },
        {
            "text": "🌸 Adding a touch of empathy to computing! Just completed a major feature update for Kazumi, my desktop companion bot. By implementing rolling emotional valence, she can now detect a user's frustration levels and offer guided breathing exercises or tuck them in with a soft body scan. Interactive companions are the future of cozy computing. 🧸✨",
            "date": "May 28, 2026",
            "url": "https://linkedin.com",
            "isMock": True
        },
        {
            "text": "🔑 Demystifying AES Encryption: A quick look at why unique Initialization Vectors (IVs) are essential. When you encrypt data with AES-256-CBC, repeating the same key-IV combo creates vulnerable patterns. By generating a fresh, cryptographically strong random IV for every entry, we secure the ciphertext against replay attacks. Simple principles make solid security!",
            "date": "May 15, 2026",
            "url": "https://linkedin.com",
            "isMock": True
        }
    ]

# ----------------------------------------------------
# 🛰️ Request Handler Class
# ----------------------------------------------------

class PortfolioRequestHandler(BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Override to prevent spamming console
        return

    def serve_static(self, file_path, content_type):
        if not os.path.exists(file_path):
            self.send_error(404, "File Not Found")
            return
        
        try:
            with open(file_path, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except Exception as e:
            self.send_error(500, f"Internal Server Error: {str(e)}")

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)
        
        # Redirect root to Kazumi Space
        if path == "/":
            self.send_response(302)
            self.send_header("Location", "/kazumi.html")
            self.end_headers()
            return

        # API Routes
        if path == "/api/settings/status":
            creds = read_credentials()
            github_cred = creds.get("github")
            linkedin_cred = creds.get("linkedin")
            status = {
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
            self.send_json(status)
            
        elif path == "/api/github/repos":
            creds = read_credentials()
            token = decrypt(creds.get("github"))
            
            if not token:
                self.send_json(get_fallback_repos())
                return
                
            # Query live GitHub API
            req = urllib.request.Request(
                "https://api.github.com/user/repos?sort=updated&per_page=6",
                headers={
                    "Authorization": f"token {token}",
                    "User-Agent": "python-portfolio-server"
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as response:
                    raw_data = json.loads(response.read().decode('utf-8'))
                    mapped = [
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
                    self.send_json(mapped)
            except Exception as e:
                print(f"GitHub Live API failed: {e}. Using fallback.")
                self.send_json(get_fallback_repos())
                
        elif path == "/api/linkedin/posts":
            creds = read_credentials()
            token = decrypt(creds.get("linkedin"))
            
            if not token:
                self.send_json(get_fallback_posts())
                return
                
            # Query live LinkedIn Shares API
            req = urllib.request.Request(
                "https://api.linkedin.com/v2/shares?q=owners&owners=urn:li:person:me&count=3",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "python-portfolio-server"
                }
            )
            try:
                with urllib.request.urlopen(req, timeout=8) as response:
                    raw_data = json.loads(response.read().decode('utf-8'))
                    mapped = [
                        {
                            "text": post.get("text", {}).get("text", "No post content."),
                            "date": "Today",
                            "url": f"https://www.linkedin.com/feed/update/{post.get('activity', '')}",
                            "isMock": False
                        }
                        for post in raw_data.get("elements", [])
                    ]
                    self.send_json(mapped)
            except Exception as e:
                print(f"LinkedIn Live API failed: {e}. Using fallback.")
                self.send_json(get_fallback_posts())
                
        elif path == "/api/kazumi/profile":
            with KAZUMI_LOCK:
                if kazumi_bot:
                    if not os.path.exists(kazumi_bot.memory.profile_path):
                        kazumi_bot.memory.save_profile()
                    self.send_json(kazumi_bot.memory.profile)
                    return
                profile_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "isa_memory", "profile.json")
                if not os.path.exists(profile_path):
                    self.send_json({"error": "Profile memory not found"})
                    return
                try:
                    with open(profile_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.send_json(data)
                except Exception as e:
                    self.send_json({"error": f"Failed to read profile: {str(e)}"})
                
        elif path == "/api/kazumi/chat":
            with KAZUMI_LOCK:
                chat_path = os.path.join(ISA_MEMORY_DIR, "conversations.json")
                if not os.path.exists(chat_path):
                    self.send_json([])
                    return
                try:
                    with open(chat_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    session_id = query.get("session_id", [None])[0]
                    if session_id:
                        data = [msg for msg in data if msg.get("session_id") == session_id]
                    self.send_json(data)
                except Exception as e:
                    self.send_json({"error": f"Failed to read chat: {str(e)}"})
                
        elif path == "/api/kazumi/history":
            with KAZUMI_LOCK:
                chat_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "isa_memory", "conversations.json")
                if not os.path.exists(chat_path):
                    self.send_json([])
                    return
                try:
                    with open(chat_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    self.send_json(data)
                except Exception as e:
                    self.send_json({"error": f"Failed to read history: {str(e)}"})
                
        elif path == "/api/kazumi/inactivity":
            with KAZUMI_LOCK:
                session_id = query.get("session_id", [None])[0]
                if not kazumi_bot:
                    self.send_json({"success": False, "error": "AI core offline"})
                    return
                try:
                    # Reload memory from disk
                    kazumi_bot.memory.history = kazumi_bot.memory.load_history()
                    kazumi_bot.memory.profile = kazumi_bot.memory.load_profile()
                    
                    reply = kazumi_bot.reply_inactivity(1, session_id=session_id)
                    self.send_json({"success": True, "reply": reply})
                except Exception as e:
                    self.send_json({"success": False, "error": f"Failed to generate inactivity response: {str(e)}"})
                
        elif path == "/api/space-info":
            self.send_json({
                "spaceId": os.environ.get("SPACE_ID")
            })
                
        else:
            # Secure path resolution against directory traversal
            base_dir = os.path.abspath("public")
            file_path = os.path.abspath(os.path.join(base_dir, path.lstrip("/")))
            if not file_path.startswith(base_dir):
                self.send_error(403, "Access Denied")
                return
                
            # Content Type Mapping
            ext = os.path.splitext(file_path)[1]
            content_type = "text/plain"
            if ext == ".html": content_type = "text/html"
            elif ext == ".css": content_type = "text/css"
            elif ext == ".js": content_type = "application/javascript"
            elif ext == ".png": content_type = "image/png"
            elif ext == ".jpg" or ext == ".jpeg": content_type = "image/jpeg"
            
            self.serve_static(file_path, content_type)

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length) if content_length > 0 else b""

        if path == "/api/settings":
            try:
                body = json.loads(post_data.decode('utf-8'))
            except Exception as e:
                self.send_error(400, f"Invalid JSON: {str(e)}")
                return
                
            creds = read_credentials()
            
            if "githubToken" in body:
                creds["github"] = encrypt(body["githubToken"]) if body["githubToken"] else None
            if "linkedinToken" in body:
                creds["linkedin"] = encrypt(body["linkedinToken"]) if body["linkedinToken"] else None
                
            save_credentials(creds)
            self.send_json({"success": True, "message": "Settings securely encrypted and saved!"})
            
        elif path == "/api/settings/clear":
            save_credentials({"github": None, "linkedin": None})
            self.send_json({"success": True, "message": "Credentials cleared."})
            
        elif path == "/api/kazumi/profile":
            with KAZUMI_LOCK:
                try:
                    body = json.loads(post_data.decode('utf-8'))
                except Exception as e:
                    self.send_error(400, f"Invalid JSON: {str(e)}")
                    return
                    
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
                            with open(profile_path, "r", encoding="utf-8") as f:
                                profile = json.load(f)
                        for k, v in body.items():
                            profile[k] = v
                        with open(profile_path, "w", encoding="utf-8") as f:
                            json.dump(profile, f, ensure_ascii=False, indent=2)
                    except Exception as e:
                        self.send_json({"success": False, "error": str(e)})
                        return
                self.send_json({"success": True, "message": "Profile synced successfully."})

        elif path == "/api/kazumi/reset":
            with KAZUMI_LOCK:
                if kazumi_bot:
                    kazumi_bot.memory.profile["cozy_points"] = 0
                    kazumi_bot.memory.profile["diary"] = []
                    kazumi_bot.memory.save_profile()
                else:
                    profile_path = os.path.join(ISA_MEMORY_DIR, "profile.json")
                    if os.path.exists(profile_path):
                        try:
                            import shutil
                            shutil.copy2(profile_path, profile_path + ".bak")
                            with open(profile_path, "r", encoding="utf-8") as f:
                                profile = json.load(f)
                            profile["cozy_points"] = 0
                            profile["diary"] = []
                            with open(profile_path, "w", encoding="utf-8") as f:
                                json.dump(profile, f, ensure_ascii=False, indent=2)
                        except Exception as e:
                            self.send_json({"success": False, "error": str(e)})
                            return
                self.send_json({"success": True, "message": "Profile reset successfully."})
            
        elif path == "/api/kazumi/chat":
            with KAZUMI_LOCK:
                try:
                    body = json.loads(post_data.decode('utf-8'))
                except Exception as e:
                    self.send_error(400, f"Invalid JSON: {str(e)}")
                    return
                    
                user_msg = body.get("message", "").strip()
                session_id = body.get("session_id", "").strip() or None
                
                if not user_msg:
                    self.send_json({"success": False, "error": "Message is empty"})
                    return
                    
                if not kazumi_bot:
                    self.send_json({"success": False, "error": "Kazumi AI Core is offline or not loaded"})
                    return
                    
                try:
                    # Reload memory from disk to capture any updates from console chats
                    kazumi_bot.memory.history = kazumi_bot.memory.load_history()
                    kazumi_bot.memory.profile = kazumi_bot.memory.load_profile()
                    
                    # Generate AI response
                    reply = kazumi_bot.reply(user_msg, session_id=session_id)
                    
                    self.send_json({"success": True, "reply": reply})
                except Exception as e:
                    self.send_json({"success": False, "error": f"Failed to generate response: {str(e)}"})
            
        else:
            self.send_error(404, "Not Found")

    def send_json(self, data):
        response_content = json.dumps(data).encode('utf-8')
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_content)))
        self.end_headers()
        self.wfile.write(response_content)


if __name__ == "__main__":
    # Force UTF-8 encoding for stdout and stderr to prevent encoding crashes on Windows console/pipes
    import sys
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8')

    # Ensure working directory is correct
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    server_address = ('', PORT)
    httpd = ThreadingHTTPServer(server_address, PortfolioRequestHandler)
    
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
    print(f"Secure Portfolio Server running on http://localhost:{PORT}")
    print(f"Local Network Share Link: http://{local_ip}:{PORT}/")
    print("Cryptography: keystream active (zero-plaintext storage)")
    print("====================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        httpd.server_close()
