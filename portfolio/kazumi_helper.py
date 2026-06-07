import sys
import io
import os
import json

# Redirect stdout to a dummy string stream immediately to swallow any prints from kazumi
dummy_stdout = io.StringIO()
sys.stdout = dummy_stdout

# Perform imports and initialization
try:
    ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    sys.path.append(ROOT_DIR)
    from kazumi import Kazumi
except Exception as e:
    # If import failed, restore stdout and exit with error
    sys.stdout = sys.__stdout__
    print(json.dumps({"success": False, "error": f"Import failed: {str(e)}"}))
    sys.exit(1)

def main():
    if len(sys.argv) < 3:
        sys.stdout = sys.__stdout__
        print(json.dumps({"success": False, "error": "Insufficient arguments"}))
        return

    command = sys.argv[1]
    session_id = sys.argv[2]
    if session_id in ("None", "undefined", "") or not session_id:
        session_id = None

    try:
        bot = Kazumi()
        # Override memory paths to use absolute root database directory
        ISA_MEMORY_DIR = os.path.join(ROOT_DIR, "isa_memory")
        bot.memory.persist_path = os.path.join(ISA_MEMORY_DIR, "conversations.json")
        bot.memory.profile_path = os.path.join(ISA_MEMORY_DIR, "profile.json")
        # Re-load memory with corrected paths
        bot.memory.history = bot.memory.load_history()
        bot.memory.profile = bot.memory.load_profile()
    except Exception as e:
        sys.stdout = sys.__stdout__
        print(json.dumps({"success": False, "error": f"Initialization failed: {str(e)}"}))
        return

    result = None
    try:
        if command == "chat":
            if len(sys.argv) < 4:
                result = {"success": False, "error": "Message body missing"}
            else:
                user_msg = sys.argv[3]
                reply = bot.reply(user_msg, session_id=session_id)
                result = {"success": True, "reply": reply}
        elif command == "inactivity":
            reply = bot.reply_inactivity(1, session_id=session_id)
            result = {"success": True, "reply": reply}
        else:
            result = {"success": False, "error": f"Unknown command: {command}"}
    except Exception as e:
        result = {"success": False, "error": f"Execution failed: {str(e)}"}

    # Restore the original system stdout to send the JSON response back to Node
    sys.stdout = sys.__stdout__
    print(json.dumps(result))

if __name__ == "__main__":
    main()
