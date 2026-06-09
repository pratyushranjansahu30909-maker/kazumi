import os
import sys
import json
import shutil
import datetime
import re
import traceback

# Setup paths
PORTFOLIO_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(PORTFOLIO_DIR)
BACKUPS_DIR = os.path.join(PORTFOLIO_DIR, "backups")
LOGS_DIR = os.path.join(PORTFOLIO_DIR, "logs")
ERROR_LOG_PATH = os.path.join(LOGS_DIR, "error_log.json")
PROPOSED_CONFIG_PATH = os.path.join(PORTFOLIO_DIR, "proposed_config.json")
VERSION_TRACK_PATH = os.path.join(PORTFOLIO_DIR, "version_track.json")

# Files to track and backup
TRACKED_FILES = [
    "kazumi.py",
    "portfolio/public/kazumi.js",
    "portfolio/server.js",
    "portfolio/server.py"
]

def init_folders():
    os.makedirs(BACKUPS_DIR, exist_ok=True)
    os.makedirs(LOGS_DIR, exist_ok=True)

def log_error(module, message, exception=None):
    init_folders()
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "module": module,
        "message": message,
        "exception": str(exception) if exception else None,
        "traceback": traceback.format_exc() if exception else None
    }
    try:
        errors = []
        if os.path.exists(ERROR_LOG_PATH):
            with open(ERROR_LOG_PATH, "r", encoding="utf-8") as f:
                errors = json.load(f)
        errors.append(entry)
        # Keep last 100 errors
        errors = errors[-100:]
        with open(ERROR_LOG_PATH, "w", encoding="utf-8") as f:
            json.dump(errors, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Failed to log error: {str(e)}")

def create_backup():
    init_folders()
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_folder = os.path.join(BACKUPS_DIR, f"backup_{timestamp}")
    os.makedirs(backup_folder, exist_ok=True)
    
    copied_files = []
    for rel_path in TRACKED_FILES:
        src = os.path.join(ROOT_DIR, rel_path.replace("/", os.sep))
        if os.path.exists(src):
            dst = os.path.join(backup_folder, os.path.basename(rel_path))
            try:
                shutil.copy2(src, dst)
                copied_files.append({
                    "original_path": rel_path,
                    "backup_name": os.path.basename(rel_path)
                })
            except Exception as e:
                log_error("BackupSystem", f"Failed to backup {rel_path}", e)
                print(f"Error backing up {rel_path}: {str(e)}")
                
    if not copied_files:
        return None
        
    version_entry = {
        "version_id": f"v_{timestamp}",
        "timestamp": datetime.datetime.now().isoformat(),
        "backup_folder": f"backup_{timestamp}",
        "files": copied_files,
        "description": "Auto backup before evaluation/config proposal"
    }
    
    try:
        track = []
        if os.path.exists(VERSION_TRACK_PATH):
            with open(VERSION_TRACK_PATH, "r", encoding="utf-8") as f:
                track = json.load(f)
        track.append(version_entry)
        with open(VERSION_TRACK_PATH, "w", encoding="utf-8") as f:
            json.dump(track, f, ensure_ascii=False, indent=2)
        print(f"Backup created successfully: version_id={version_entry['version_id']}")
        return version_entry["version_id"]
    except Exception as e:
        log_error("BackupSystem", "Failed to update version tracking ledger", e)
        print(f"Error updating version track: {str(e)}")
        return None

def rollback():
    if not os.path.exists(VERSION_TRACK_PATH):
        print("No version history found. Cannot rollback.")
        return
        
    try:
        with open(VERSION_TRACK_PATH, "r", encoding="utf-8") as f:
            track = json.load(f)
            
        if not track:
            print("No backups recorded in tracking ledger.")
            return
            
        last_backup = track[-1]
        backup_folder = os.path.join(BACKUPS_DIR, last_backup["backup_folder"])
        if not os.path.exists(backup_folder):
            print(f"Backup folder {last_backup['backup_folder']} is missing. Rollback failed.")
            return
            
        print(f"Rolling back to version {last_backup['version_id']} from {last_backup['timestamp']}...")
        
        for file_info in last_backup["files"]:
            src = os.path.join(backup_folder, file_info["backup_name"])
            dst = os.path.join(ROOT_DIR, file_info["original_path"].replace("/", os.sep))
            if os.path.exists(src):
                # Ensure destination directory exists
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.copy2(src, dst)
                print(f"Restored: {file_info['original_path']}")
                
        # Remove rolled back entry from track list
        track.pop()
        with open(VERSION_TRACK_PATH, "w", encoding="utf-8") as f:
            json.dump(track, f, ensure_ascii=False, indent=2)
            
        print("Rollback completed successfully!")
    except Exception as e:
        log_error("RollbackSystem", "Failed to perform rollback operation", e)
        print(f"Error during rollback: {str(e)}")

def evaluate_performance():
    stress_log_path = os.path.join(PORTFOLIO_DIR, "stress_test_log.json")
    if not os.path.exists(stress_log_path):
        return {
            "status": "No stress logs found. Run python portfolio/test_stress.py first.",
            "average_latency_ms": 0,
            "success_rate": 0,
            "total_runs": 0,
            "failures": []
        }
        
    try:
        with open(stress_log_path, "r", encoding="utf-8") as f:
            logs = json.load(f)
            
        total = len(logs)
        passed = sum(1 for item in logs if item.get("success", False))
        latencies = [item.get("latency_ms", 0) for item in logs]
        avg_lat = sum(latencies) / total if total > 0 else 0
        success_rate = (passed / total) * 100 if total > 0 else 0
        
        failures = [item for item in logs if not item.get("success", False)]
        
        return {
            "status": "Success",
            "average_latency_ms": int(avg_lat),
            "success_rate": round(success_rate, 2),
            "total_runs": total,
            "failures": failures
        }
    except Exception as e:
        log_error("PerformanceMonitor", "Failed to evaluate stress test logs", e)
        return {"status": f"Error: {str(e)}", "average_latency_ms": 0, "success_rate": 0, "total_runs": 0, "failures": []}

def evaluate_quality():
    stress_log_path = os.path.join(PORTFOLIO_DIR, "stress_test_log.json")
    conversations_path = os.path.join(ROOT_DIR, "isa_memory", "conversations.json")
    
    all_responses = []
    
    # 1. Gather from stress logs
    if os.path.exists(stress_log_path):
        try:
            with open(stress_log_path, "r", encoding="utf-8") as f:
                logs = json.load(f)
                for item in logs:
                    if item.get("response"):
                        all_responses.append(item["response"])
        except Exception:
            pass
            
    # 2. Gather from user conversations
    if os.path.exists(conversations_path):
        try:
            with open(conversations_path, "r", encoding="utf-8") as f:
                history = json.load(f)
                for item in history:
                    if item.get("speaker") == "kazumi" and item.get("text"):
                        all_responses.append(item["text"])
        except Exception:
            pass
            
    if not all_responses:
        return {
            "repetitions": [],
            "average_words": 0,
            "briefness_adherence": 100.0,
            "stilted_sentences": []
        }
        
    word_counts = []
    repeated_phrases = {}
    stilted_samples = []
    
    for resp in all_responses:
        clean_resp = re.sub(r'\(.*?\)', '', resp).strip() # strip emoji/actions
        words = clean_resp.split()
        word_counts.append(len(words))
        
        # Check for repetitive 3-word n-grams
        words_lower = [w.lower().strip(".,!?\"'") for w in words]
        for i in range(len(words_lower) - 2):
            phrase = " ".join(words_lower[i:i+3])
            if len(phrase) > 10:
                repeated_phrases[phrase] = repeated_phrases.get(phrase, 0) + 1
                
        # Heuristic check for awkward/stilted patterns
        if len(words) > 30 and ("hello" in clean_resp.lower() or "sweetie" in clean_resp.lower()):
            # Fallback patterns are usually longer and generic
            if any(f in clean_resp for f in ["really interesting", "makes a lot of sense", "always right here"]):
                stilted_samples.append(resp)
                
    avg_words = sum(word_counts) / len(word_counts) if word_counts else 0
    
    # Repetition score (phrases appearing > 2 times)
    reps = [{"phrase": k, "count": v} for k, v in repeated_phrases.items() if v > 2]
    reps = sorted(reps, key=lambda x: x["count"], reverse=True)[:5]
    
    # Brevity adherence: percent of responses <= 30 words (target for punchy responses)
    short_responses = sum(1 for count in word_counts if count <= 30)
    brevity_pct = (short_responses / len(word_counts)) * 100 if word_counts else 100.0
    
    return {
        "repetitions": reps,
        "average_words": round(avg_words, 1),
        "briefness_adherence": round(brevity_pct, 2),
        "stilted_sentences": list(set(stilted_samples))[:5]
    }

def run_openai_optimizer(perf_results, qual_results):
    # Retrieve OpenAI API Key from environment or .env files
    api_key = os.environ.get("API_KEY", "")
    if not api_key:
        for env_path in [os.path.join(ROOT_DIR, ".env"), os.path.join(PORTFOLIO_DIR, ".env")]:
            if os.path.exists(env_path):
                try:
                    with open(env_path, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.strip() and "=" in line:
                                k, v = line.strip().split("=", 1)
                                if k.strip() == "API_KEY":
                                    api_key = v.strip().strip('"').strip("'")
                                    break
                except Exception:
                    pass
            if api_key:
                break
                
    if not api_key:
        print("API_KEY not found in environment. Generating template config recommendations locally.")
        return generate_local_optimizations(perf_results, qual_results)
        
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        
        prompt = f"""
You are an expert AI prompt engineer and system optimizer.
Analyze the following Kazumi Companion AI metrics:

Performance metrics:
- Latency (avg): {perf_results['average_latency_ms']} ms
- Success Rate: {perf_results['success_rate']}%
- Total Test Runs: {perf_results['total_runs']}
- Success status: {perf_results['status']}

Quality metrics:
- Average word count: {qual_results['average_words']} words (Goal: 10-25 words for punchy chat)
- Repetitive phrases found: {json.dumps(qual_results['repetitions'])}
- Brevity adherence rate: {qual_results['briefness_adherence']}%
- Long or stilted fallback sentences: {json.dumps(qual_results['stilted_sentences'])}

Please output a structured JSON containing proposed configuration optimizations.
Format your response exactly as follows:
{{
  "proposed_temperature": float (e.g., 0.75),
  "proposed_frequency_penalty": float (e.g., 0.6),
  "proposed_presence_penalty": float (e.g., 0.4),
  "recommended_prompt_additions": [
    "string rule 1 to append to system prompt",
    "string rule 2 to append to system prompt"
  ],
  "reasoning": "A paragraph explaining why these changes help reduce repetition, manage latency, and optimize conversational flow."
}}
Return ONLY raw JSON. Do not include markdown codeblocks or extra text.
"""
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": "You are a JSON-only configuration generator."},
                      {"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=600
        )
        
        text = response.choices[0].message.content.strip()
        # Clean potential markdown output
        text = re.sub(r"^```json", "", text, flags=re.IGNORECASE)
        text = re.sub(r"```$", "", text, flags=re.IGNORECASE).strip()
        
        proposed = json.loads(text)
        return proposed
    except Exception as e:
        log_error("Optimizer", "Failed to call OpenAI API for prompt optimization", e)
        print(f"OpenAI call failed, falling back to local optimization presets: {str(e)}")
        return generate_local_optimizations(perf_results, qual_results)

def generate_local_optimizations(perf_results, qual_results):
    # Local Rule-based heuristics to recommend optimizations
    temp = 0.7
    freq_penalty = 0.5
    pres_penalty = 0.3
    additions = []
    reasoning = "Generated via built-in diagnostic rule engine."
    
    if qual_results["average_words"] > 25:
        additions.append("Strictly limit replies to under 20 words where possible.")
        reasoning += " High average word count triggered stricter brevity instructions."
        
    if len(qual_results["repetitions"]) > 0:
        freq_penalty = 0.65
        pres_penalty = 0.45
        additions.append("Never reuse the same sentence structures or phrases from the rolling history.")
        reasoning += " Vocabulary repetitions triggered higher frequency and presence penalties."
        
    if perf_results["average_latency_ms"] > 3500:
        temp = 0.6
        additions.append("Prioritize rapid responses. Keep responses single-clause and crisp.")
        reasoning += " High average latency triggered a lower temperature for faster completions."
        
    return {
        "proposed_temperature": temp,
        "proposed_frequency_penalty": freq_penalty,
        "proposed_presence_penalty": pres_penalty,
        "recommended_prompt_additions": additions if additions else ["Keep responses warm, short, and dynamic."],
        "reasoning": reasoning
    }

def run_diagnostics():
    init_folders()
    print("====================================================")
    print("[Diagnostics] Running Kazumi Quality & Performance Diagnostics")
    print("====================================================")
    
    # 1. Performance logs analysis
    perf = evaluate_performance()
    print(f"Performance Status: {perf['status']}")
    print(f"Average Latency   : {perf['average_latency_ms']} ms")
    print(f"Success Rate      : {perf['success_rate']}%")
    
    # 2. Response quality analysis
    qual = evaluate_quality()
    print(f"Average Reply Len : {qual['average_words']} words")
    print(f"Brevity Adherence : {qual['briefness_adherence']}%")
    if qual["repetitions"]:
        print("Repetitive phrases detected:")
        for r in qual["repetitions"]:
            print(f"  - '{r['phrase']}' (seen {r['count']} times)")
            
    # 3. Create a safety backup
    create_backup()
    
    # 4. Generate recommendations
    proposed = run_openai_optimizer(perf, qual)
    
    with open(PROPOSED_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(proposed, f, ensure_ascii=False, indent=2)
        
    print("\nProposed Configuration Optimizations:")
    print(f"  - Temperature: {proposed.get('proposed_temperature')}")
    print(f"  - Frequency Penalty: {proposed.get('proposed_frequency_penalty')}")
    print(f"  - Presence Penalty: {proposed.get('proposed_presence_penalty')}")
    print(f"  - Recommended rules:")
    for rule in proposed.get("recommended_prompt_additions", []):
        print(f"    * {rule}")
    print(f"  - Reasoning: {proposed.get('reasoning')}")
    print(f"\nRecommendations successfully written to [proposed_config.json](file:///{PROPOSED_CONFIG_PATH.replace(os.sep, '/')})")
    print("====================================================")

if __name__ == "__main__":
    if "--rollback" in sys.argv:
        rollback()
    else:
        run_diagnostics()
