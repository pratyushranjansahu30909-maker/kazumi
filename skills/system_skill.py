import subprocess
from .base_skill import KazumiSkill

class SystemSkill(KazumiSkill):
    def get_triggers(self):
        return [
            r"^/sys",
            r"\b(lock my screen|lock the screen|lock computer|lock workstation|lock the computer|lock pc)\b",
            r"\b(shutdown the computer|shut down my computer|turn off the pc|shutdown pc|turn off computer)\b",
            r"\b(restart the computer|reboot the computer|restart my pc|restart computer|reboot computer)\b",
            r"\b(abort shutdown|cancel shutdown|stop shutdown|abort restart|cancel restart)\b"
        ]

    def get_help(self):
        return "/sys <lock/shutdown/restart/abort>", "Run system actions like workstation locking or power controls."

    def handle(self, text, clean_text, valence):
        intent_text = clean_text.lower().strip()
        
        # 1. Standard CLI style slash command
        if intent_text.startswith("/sys"):
            parts = intent_text.split()
            if len(parts) < 2:
                return "(Kazumi looks at you, surprised...) You want to run a system action? 🖥️ " \
                       "Please specify which action! You can say `/sys lock`, `/sys shutdown`, `/sys restart`, or `/sys abort`! 🌸"
            arg = parts[1].strip()
        else:
            # 2. Natural language mapping
            if any(p in intent_text for p in ["lock my screen", "lock the screen", "lock computer", "lock workstation", "lock the computer", "lock pc"]):
                arg = "lock"
            elif any(p in intent_text for p in ["shutdown the computer", "shut down my computer", "turn off the pc", "shutdown pc", "turn off computer"]):
                arg = "shutdown"
            elif any(p in intent_text for p in ["restart the computer", "reboot the computer", "restart my pc", "restart computer", "reboot computer"]):
                arg = "restart"
            elif any(p in intent_text for p in ["abort shutdown", "cancel shutdown", "stop shutdown", "abort restart", "cancel restart"]):
                arg = "abort"
            else:
                return None

        # Execute system action
        try:
            if arg == "lock":
                subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
                return "(Kazumi locks the screen and waves goodbye...) Workstation locked! See you soon, sweetie! 🔒💤"
            elif arg == "shutdown":
                subprocess.Popen(["shutdown", "/s", "/t", "60"])
                return "(Kazumi looks worried...) Triggering system shutdown in 60 seconds! ⚠️ " \
                       "If you made a mistake, quickly say `/sys abort` to stop it! ⚠️"
            elif arg == "restart":
                subprocess.Popen(["shutdown", "/r", "/t", "60"])
                return "(Kazumi prepares to restart...) Triggering system restart in 60 seconds! ⚠️ " \
                       "If you made a mistake, quickly say `/sys abort` to stop it! ⚠️"
            elif arg == "abort":
                subprocess.Popen(["shutdown", "/a"])
                return "(Kazumi sighs with relief...) Ah, shutdown/restart sequence aborted! I'm glad you're staying! 🌸💖"
            else:
                return "Unknown system action. Try `/sys lock`, `/sys shutdown`, `/sys restart`, or `/sys abort`! 🌸"
        except Exception as e:
            return f"System command failed: {e}"
