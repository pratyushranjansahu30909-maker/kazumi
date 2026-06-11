import os
import sys
import json
import time
import shutil
import unittest

# Resolve absolute pathways
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from kazumi import Kazumi, ChromaMemory

class TestStartupProtection(unittest.TestCase):
    def setUp(self):
        # We will use a dedicated test memory directory to avoid clobbering production memory
        self.test_dir = os.path.join(ROOT_DIR, "test_isa_memory")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        
        # Override persist paths dynamically
        self.profile_path = os.path.join(self.test_dir, "profile.json")
        self.history_path = os.path.join(self.test_dir, "conversations.json")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            try:
                shutil.rmtree(self.test_dir)
            except Exception:
                pass

    def test_startup_preserves_existing_data(self):
        print("Running test: test_startup_preserves_existing_data")
        # 1. Write mock non-default user data
        mock_profile = {
            "_schema_version": 1,
            "name": "Alex",
            "affection_level": 37,
            "cozy_points": 84,
            "diary": ["Entry A", "Entry B"],
            "_is_default": False
        }
        mock_history = [
            {"text": "Hello Kazumi!", "speaker": "user", "valence": 0.5, "timestamp": time.time(), "session_id": "test"}
        ]
        
        with open(self.profile_path, "w", encoding="utf-8") as f:
            json.dump(mock_profile, f)
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(mock_history, f)

        # 2. Initialize ChromaMemory pointing to this directory
        memory = ChromaMemory(persist_directory=self.test_dir)
        
        # 3. Assert values were NOT reset to defaults on startup
        self.assertEqual(memory.profile["affection_level"], 37)
        self.assertEqual(memory.profile["cozy_points"], 84)
        self.assertEqual(memory.profile["name"], "Alex")
        self.assertEqual(memory.profile["diary"], ["Entry A", "Entry B"])
        self.assertEqual(len(memory.history), 1)
        self.assertEqual(memory.history[0]["text"], "Hello Kazumi!")

    def test_crash_recovery_from_backup(self):
        print("Running test: test_crash_recovery_from_backup")
        # 1. Write a correct backup profile
        mock_backup = {
            "_schema_version": 1,
            "name": "Alex",
            "affection_level": 42,
            "cozy_points": 90,
            "diary": ["Recovered Entry"],
            "_is_default": False
        }
        with open(self.profile_path + ".bak", "w", encoding="utf-8") as f:
            json.dump(mock_backup, f)
            
        # 2. Write a corrupted main profile file
        with open(self.profile_path, "w", encoding="utf-8") as f:
            f.write("{ corrupt json: [ ")

        # 3. Initialize ChromaMemory pointing to this directory
        memory = ChromaMemory(persist_directory=self.test_dir)

        # 4. Verify that:
        # a) Corrupted file was archived (renamed to .corrupted.[timestamp])
        files = os.listdir(self.test_dir)
        corrupted_files = [f for f in files if "profile.json.corrupted." in f]
        self.assertTrue(len(corrupted_files) >= 1, f"Expected corrupted file archive, found: {files}")

        # b) State was successfully recovered from the backup file
        self.assertEqual(memory.profile["affection_level"], 42)
        self.assertEqual(memory.profile["cozy_points"], 90)
        self.assertEqual(memory.profile["diary"], ["Recovered Entry"])

    def test_empty_state_initializes_defaults_with_is_default_flag(self):
        print("Running test: test_empty_state_initializes_defaults_with_is_default_flag")
        # Initialize memory with no files on disk (clean startup scenario)
        memory = ChromaMemory(persist_directory=self.test_dir)
        
        # Verify default profile loaded
        self.assertEqual(memory.profile["affection_level"], 0)
        self.assertEqual(memory.profile["cozy_points"], 0)
        self.assertTrue(memory.profile["_is_default"])

        # Save profile
        memory.save_profile()
        
        # Verify that _is_default is set to False after saving
        self.assertFalse(memory.profile["_is_default"])
        
        # Load again from disk and verify _is_default is indeed False
        memory_reboot = ChromaMemory(persist_directory=self.test_dir)
        self.assertFalse(memory_reboot.profile["_is_default"])

    def test_client_restore_sync(self):
        print("Running test: test_client_restore_sync")
        # Simulate the client sync logic
        # 1. Server returns a default profile on startup
        memory = ChromaMemory(persist_directory=self.test_dir)
        server_profile = memory.profile # has _is_default: True
        
        # 2. Client has an existing profile in localStorage with progress
        client_profile = {
            "_schema_version": 1,
            "name": "Friend",
            "affection_level": 30, # Higher than default (0), but user's real progress!
            "cozy_points": 80,    # Higher than default (0)
            "diary": ["A lovely day"],
            "_is_default": False
        }
        
        # 3. Simulate public/kazumi.js sync check logic:
        # If server profile is marked default, restore full client profile
        needs_sync = False
        if server_profile.get("_is_default") and not client_profile.get("_is_default"):
            server_profile = dict(client_profile)
            server_profile["_is_default"] = False
            needs_sync = True
            
        self.assertTrue(needs_sync)
        self.assertEqual(server_profile["affection_level"], 30)
        self.assertEqual(server_profile["cozy_points"], 80)
        self.assertEqual(server_profile["diary"], ["A lovely day"])
        self.assertFalse(server_profile["_is_default"])

    def test_split_storage_endpoints(self):
        print("Running test: test_split_storage_endpoints")
        # 1. Simulate POST profile offline logic (updating profile and splitting diary)
        body = {
            "name": "Alex",
            "affection_level": 60,
            "cozy_points": 120,
            "diary": ["A beautiful morning", "A lovely afternoon"]
        }
        
        # Write to profile.json (mocking how the server merges incoming request to profile)
        profile_path = os.path.join(self.test_dir, "profile.json")
        diary_path = os.path.join(self.test_dir, "diary.json")
        
        profile = {}
        for k, v in body.items():
            profile[k] = v
            
        # Split storage logic:
        if "diary" in profile:
            diary = profile["diary"]
            with open(diary_path, "w", encoding="utf-8") as f:
                json.dump(diary, f, indent=2)
            del profile["diary"]
            
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
            
        # Verify split on disk
        with open(profile_path, "r", encoding="utf-8") as f:
            profile_data = json.load(f)
        self.assertNotIn("diary", profile_data)
        self.assertEqual(profile_data["name"], "Alex")
        
        with open(diary_path, "r", encoding="utf-8") as f:
            diary_data = json.load(f)
        self.assertEqual(diary_data, ["A beautiful morning", "A lovely afternoon"])
        
        # 2. Simulate GET profile offline logic (reading and merging)
        with open(profile_path, "r", encoding="utf-8") as f:
            get_data = json.load(f)
            
        diary_loaded = None
        if os.path.exists(diary_path):
            with open(diary_path, "r", encoding="utf-8") as f:
                diary_loaded = json.load(f)
        if diary_loaded is None:
            diary_loaded = []
            
        get_data["diary"] = diary_loaded
        
        self.assertEqual(get_data["name"], "Alex")
        self.assertEqual(get_data["diary"], ["A beautiful morning", "A lovely afternoon"])
        
        # 3. Simulate POST reset offline logic
        with open(profile_path, "r", encoding="utf-8") as f:
            reset_profile = json.load(f)
            
        reset_profile["cozy_points"] = 0
        with open(diary_path, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
            
        if "diary" in reset_profile:
            del reset_profile["diary"]
            
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(reset_profile, f, indent=2)
            
        # Verify reset results
        with open(profile_path, "r", encoding="utf-8") as f:
            final_profile = json.load(f)
        self.assertEqual(final_profile["cozy_points"], 0)
        self.assertNotIn("diary", final_profile)
        
        with open(diary_path, "r", encoding="utf-8") as f:
            final_diary = json.load(f)
        self.assertEqual(final_diary, [])

if __name__ == "__main__":
    unittest.main()
