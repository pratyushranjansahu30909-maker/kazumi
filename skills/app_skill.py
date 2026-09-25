import subprocess
import webbrowser
from .base_skill import KazumiSkill

class AppSkill(KazumiSkill):
    def get_triggers(self):
        return [
            r"^/app",
            r"\b(open notepad|start notepad|launch notepad|open a new notepad)\b",
            r"\b(open calculator|start calculator|launch calculator|open calc|start calc)\b",
            r"\b(open browser|start browser|launch browser|open default browser|open google)\b",
            r"\b(open terminal|start terminal|open cmd|open command prompt|start command prompt)\b"
        ]

    def get_help(self):
        return "/app <notepad/calc/browser/cmd>", "Launch utility applications asynchronously."

    def handle(self, text, clean_text, valence):
        intent_text = clean_text.lower().strip()
        
        # 1. Standard CLI style slash command
        if intent_text.startswith("/app"):
            parts = intent_text.split()
            if len(parts) < 2:
                return "(Kazumi gets ready to open an app...) Ooh, what application would you like to open? " \
                       "You can tell me `/app notepad`, `/app calc`, `/app browser`, or `/app cmd`! 🌸"
            arg = parts[1].strip()
        else:
            # 2. Natural language mapping
            if any(p in intent_text for p in ["open notepad", "start notepad", "launch notepad", "open a new notepad"]):
                arg = "notepad"
            elif any(p in intent_text for p in ["open calculator", "start calculator", "launch calculator", "open calc", "start calc"]):
                arg = "calc"
            elif any(p in intent_text for p in ["open browser", "start browser", "launch browser", "open default browser", "open google"]):
                arg = "browser"
            elif any(p in intent_text for p in ["open terminal", "start terminal", "open cmd", "open command prompt", "start command prompt"]):
                arg = "cmd"
            else:
                return None

        # Execute application launch
        try:
            if arg == "notepad":
                subprocess.Popen(["notepad.exe"])
                return "(Kazumi opens Notepad for you...) Here is a fresh notepad page for your thoughts! 📝"
            elif arg == "calc":
                subprocess.Popen(["calc.exe"])
                return "(Kazumi opens the calculator...) Calculator ready for some quick math! 🔢"
            elif arg == "browser":
                webbrowser.open("https://google.com")
                return "(Kazumi opens your default browser...) Browser opened! Ready to explore? 🌐"
            elif arg == "cmd":
                subprocess.Popen(["cmd.exe"], creationflags=subprocess.CREATE_NEW_CONSOLE)
                return "(Kazumi spawns a terminal window...) Command Prompt opened, ready for commands! 💻"
            else:
                return "I don't know how to open that application yet. Try `/app notepad`, `/app calc`, `/app browser`, or `/app cmd`! 🌸"
        except Exception as e:
            return f"Failed to open application: {e}"
