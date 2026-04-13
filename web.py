import os
import json
import subprocess
import logging
import shlex
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# ==========================================
# SYSTEM CONFIGURATION & LOGGING
# ==========================================
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("WebDashboard")

app = Flask(__name__)

REGISTRY_FILE = os.getenv('REGISTRY_FILE', 'watchdog_registry.json')

def load_registry():
    """Loads the bot registry safely."""
    if not os.path.exists(REGISTRY_FILE):
        return {"BOTS": {}}
    try:
        with open(REGISTRY_FILE, 'r') as f: 
            return json.load(f)
    except json.JSONDecodeError:
        return {"BOTS": {}}

def get_bot_status():
    """Checks the server to see which bots are currently running."""
    reg = load_registry()
    try:
        # Using a list for subprocess arguments is safer than a raw shell string
        output = subprocess.check_output(["ps", "aux"], text=True)
    except Exception as e:
        logger.error(f"Failed to read processes: {e}")
        output = ""
        
    status_data = {}
    for key, bot in reg.get('BOTS', {}).items():
        bot_file = bot.get('file', '')
        is_running = f"python3 -u {bot_file}" in output
        
        status_data[key] = {
            "name": bot.get('name', key),
            "file": bot_file,
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
    data = request.json or {}
    action = data.get('action') # 'start' or 'stop'
    reg = load_registry()
    
    if bot_key not in reg.get('BOTS', {}):
        return jsonify({"success": False, "error": "Bot not found"}), 404
        
    bot_file = reg['BOTS'][bot_key]['file']
    log_file = reg['BOTS'][bot_key].get('log', f"{bot_key}_log.txt")
    
    # SECURITY: Sanitize filenames so hackers cannot execute malicious shell commands
    safe_bot_file = shlex.quote(bot_file)
    safe_log_file = shlex.quote(log_file)
    
    kill_cmd = f"pkill -f 'python3 -u {safe_bot_file}'"
    
    try:
        if action == 'stop':
            subprocess.run(kill_cmd, shell=True)
            return jsonify({"success": True, "new_status": "Offline"})
            
        elif action == 'start':
            subprocess.run(kill_cmd, shell=True) # Kill ghost processes first
            subprocess.Popen(f"nohup python3 -u {safe_bot_file} > {safe_log_file} 2>&1 &", shell=True)
            return jsonify({"success": True, "new_status": "Online"})
            
    except Exception as e:
        logger.error(f"Failed to toggle bot: {e}")
        return jsonify({"success": False, "error": "Server error"}), 500

if __name__ == '__main__':
    # Pull port from environment, fallback to 5000
    port = int(os.getenv('FLASK_PORT', 5000))
    is_debug = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    
    logger.info(f"🌐 Web Dashboard starting on Port {port}...")
    app.run(host='0.0.0.0', port=port, debug=is_debug)
