import os
import json
import subprocess
import logging
from flask import Flask, render_template, request, jsonify

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WebCMS")

app = Flask(__name__)

REGISTRY_FILE = 'watchdog_registry.json'

def load_registry():
    if not os.path.exists(REGISTRY_FILE):
        return {"BOTS": {}}
    with open(REGISTRY_FILE, 'r') as f: 
        return json.load(f)

def get_bot_status():
    """Checks the server to see which bots are currently running."""
    reg = load_registry()
    try:
        output = subprocess.check_output("ps aux", shell=True).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to read process list: {e}")
        output = ""
        
    status_data = {}
    for key, bot in reg.get('BOTS', {}).items():
        is_running = f"python3 -u {bot['file']}" in output
        status_data[key] = {
            "name": bot['name'],
            "file": bot['file'],
            "status": "Online" if is_running else "Offline",
            "color": "text-green-500" if is_running else "text-red-500",
            "bg_color": "bg-green-500" if is_running else "bg-red-500"
        }
    return status_data

@app.route('/')
def dashboard():
    """Loads the main webpage."""
    bots = get_bot_status()
    return render_template('index.html', bots=bots)

@app.route('/api/toggle/<bot_key>', methods=['POST'])
def toggle_bot(bot_key):
    """API endpoint to start or stop a bot from the web button."""
    data = request.json
    action = data.get('action') # 'start' or 'stop'
    reg = load_registry()
    
    if bot_key not in reg.get('BOTS', {}):
        return jsonify({"success": False, "error": "Bot not found"})
        
    bot_file = reg['BOTS'][bot_key]['file']
    log_file = reg['BOTS'][bot_key]['log']
    kill_cmd = f"pkill -f 'python3 -u {bot_file}'"
    
    try:
        if action == 'stop':
            subprocess.run(kill_cmd, shell=True)
            logger.info(f"Stopped bot: {bot_file}")
            return jsonify({"success": True, "new_status": "Offline"})
            
        elif action == 'start':
            subprocess.run(kill_cmd, shell=True) # Kill ghost processes first
            subprocess.Popen(f"nohup python3 -u {bot_file} > {log_file} 2>&1 &", shell=True)
            logger.info(f"Started bot: {bot_file}")
            return jsonify({"success": True, "new_status": "Online"})
            
    except Exception as e:
        logger.error(f"Failed to toggle bot {bot_key}: {e}")
        return jsonify({"success": False, "error": str(e)})

if __name__ == '__main__':
    logger.info("🌐 Web Dashboard starting on Port 5000...")
    # debug=False is crucial for production to prevent arbitrary code execution
    app.run(host='0.0.0.0', port=5000, debug=False)
