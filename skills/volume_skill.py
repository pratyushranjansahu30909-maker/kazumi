import re
import subprocess
from .base_skill import KazumiSkill

class VolumeSkill(KazumiSkill):
    def get_triggers(self):
        return [
            r"^/volume",
            r"\b(volume up|increase volume|louder|turn it up|volume down|decrease volume|quieter|turn it down|mute computer|mute volume|unmute computer|unmute volume)\b",
            r"\b(set|change|put|turn)\s+(?:the\s+)?volume\s+(?:to\s+)?\d+\b",
            r"\bvolume\s+\d+\b"
        ]

    def get_help(self):
        return "/volume <up/down/mute/unmute/0-100>", "Adjust system volume or mute settings."

    def handle(self, text, clean_text, valence):
        intent_text = clean_text.lower().strip()
        
        # 1. Standard CLI style slash command
        if intent_text.startswith("/volume"):
            parts = intent_text.split()
            if len(parts) < 2:
                return "(Kazumi tilts her head...) You want to adjust the volume? 🎧 " \
                       "Please tell me what to do! You can say `/volume up`, `/volume down`, " \
                       "`/volume mute`, `/volume unmute`, or set a specific percentage like `/volume 50`! 😊"
            arg = parts[1].strip()
        else:
            # 2. Natural language mapping
            if any(p in intent_text for p in ["turn up the volume", "turn the volume up", "volume up", "increase the volume", "increase volume", "make it louder", "turn it up"]):
                arg = "up"
            elif any(p in intent_text for p in ["turn down the volume", "turn the volume down", "volume down", "decrease the volume", "decrease volume", "make it quieter", "turn it down"]):
                arg = "down"
            elif any(p in intent_text for p in ["mute the computer", "mute computer", "mute the volume", "mute volume", "silence the volume"]):
                arg = "mute"
            elif any(p in intent_text for p in ["unmute the computer", "unmute computer", "unmute the volume", "unmute volume"]):
                arg = "unmute"
            else:
                vol_pct_match = re.search(r"(?:set|change|put|turn)\s+(?:the\s+)?volume\s+(?:to\s+)?(\d+)", intent_text) or re.search(r"volume\s+(\d+)", intent_text)
                if vol_pct_match:
                    arg = vol_pct_match.group(1)
                else:
                    return None

        # Execute volume command
        try:
            if arg == "up":
                subprocess.Popen(["powershell", "-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]175)"])
                return "(Kazumi reaches for the dials...) Volume turned up! 🔊✨"
            elif arg == "down":
                subprocess.Popen(["powershell", "-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]174)"])
                return "(Kazumi turns the dial down...) Volume turned down! 🔉"
            elif arg in ["mute", "unmute"]:
                subprocess.Popen(["powershell", "-Command", "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"])
                return f"(Kazumi taps the mute button...) Volume {arg}d! 🔇🔊"
            elif arg.isdigit():
                val = int(arg)
                if 0 <= val <= 100:
                    cmd = f"$w = New-Object -ComObject WScript.Shell; for($i=0; $i -lt 50; $i++) {{ $w.SendKeys([char]174) }}; for($i=0; $i -lt {val // 2}; $i++) {{ $w.SendKeys([char]175) }}"
                    subprocess.Popen(["powershell", "-Command", cmd])
                    return f"(Kazumi adjusts the slider...) Volume set to {val}%! 🎛️🌸"
                else:
                    return "Oops! Please specify a volume percentage between 0 and 100, sweetie! 🌸"
            else:
                return "Oops! I didn't quite understand that volume setting. Try `/volume up`, `/volume down`, or a percentage like `/volume 50`! 🌸"
        except Exception as e:
            return f"Failed to adjust volume: {e}"
