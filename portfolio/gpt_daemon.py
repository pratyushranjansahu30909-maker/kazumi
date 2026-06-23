import os
import sys
import time

# Custom import path to include portfolio
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from gpt_server_manager import GPTServerManager

def main():
    manager = GPTServerManager()
    print("GPT-SoVITS background manager daemon started...")
    
    # Try auto starting if environment is ready
    if manager.check_weights_exist() and manager.check_python_dependencies():
        manager.start_server()
        
    # Sleep forever to keep monitoring alive
    try:
        while True:
            time.sleep(10)
    except KeyboardInterrupt:
        print("Stopping daemon...")
        manager.stop_server()

if __name__ == "__main__":
    main()
