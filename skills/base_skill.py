import os
import importlib.util
import inspect

class KazumiSkill:
    def __init__(self, bot):
        self.bot = bot

    def get_triggers(self):
        """Returns a list of regular expressions that trigger this skill."""
        return []

    def get_help(self):
        """Returns helper details (trigger command, description)."""
        return "", ""

    def handle(self, text, clean_text, valence):
        """Processes the input text and returns a string reply or None if it should fall through."""
        return None

class SkillManager:
    def __init__(self, bot):
        self.bot = bot
        self.skills = []
        self.load_skills()

    def load_skills(self):
        self.skills = []
        skills_dir = os.path.dirname(os.path.abspath(__file__))
        
        if not os.path.exists(skills_dir):
            return

        for filename in os.listdir(skills_dir):
            if filename.endswith(".py") and filename not in ["__init__.py", "base_skill.py"]:
                module_name = f"skills.{filename[:-3]}"
                filepath = os.path.join(skills_dir, filename)
                try:
                    spec = importlib.util.spec_from_file_location(module_name, filepath)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    for name, obj in inspect.getmembers(module):
                        if inspect.isclass(obj) and issubclass(obj, KazumiSkill) and obj != KazumiSkill:
                            skill_inst = obj(self.bot)
                            self.skills.append(skill_inst)
                            print(f"[Skill Manager] Loaded skill: {name}")
                except Exception as e:
                    print(f"[Skill Manager Warning] Failed to load skill from {filename}: {e}")
