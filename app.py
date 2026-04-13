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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WebCMS")

app = Flask(__name__)

# Allow users to define a custom registry path, fallback to default
REGISTRY_FILE = os.getenv('REGISTRY_FILE', 'watchdog_registry.json')

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def load_registry():
    """Loads the bot registry safely, returning an empty template on failure."""
    if not os.path.exists(REGISTRY_FILE):
        logger.warning(f"Registry file '{REGISTRY_FILE}' not found. Returning empty registry.")
        return {"BOTS": {}}
        
    try:
        with open(REGISTRY_FILE, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse registry JSON: {e}")
        return {"BOTS": {}}

def get_bot_status():
    """Checks the server to see which bots are currently running."""
    reg = load_registry()
    
    try:
        # Use a list for subprocess arguments when possible for better security
        output = subprocess.check_output(["ps", "aux"], text=True)
    except Exception as e:
        logger.error(f"Failed to retrieve process list: {e}")
        output = ""
        
    status_data = {}
    for key, bot in reg.get('BOTS', {}).items():
        bot_name = bot.get('name', 'Unknown Bot')
        bot_file = bot.get('file', '')
        
        if not bot_file:
            continue
            
        is_running = f"python3 -u {bot_file}" in output
        
        status_data[key] = {
            "name": bot_name,
            "file": bot_file,
            "status": "Online" if is_running else "Offline",
            "color": "text-green-500" if is_running else "text-red-500",
            "bg_color": "bg-green-500" if is_running else "bg-red-500"
        }
        
    return status_data

# ==========================================
# FLASK ROUTES
# ==========================================
@app.route('/')
def dashboard():
    """Loads the main webpage."""
    bots = get_bot_status()
    return render_template('index.html', bots=bots)

@app.route('/api/toggle/<bot_key>', methods=['POST'])
def toggle_bot(bot_key):
    """API endpoint to start or stop a bot from the web dashboard."""
    data = request.json or {}
    action = data.get('action') # Expected: 'start' or 'stop'
    
    if action not in ['start', 'stop']:
        return jsonify({"success": False, "error": "Invalid action requested"}), 400

    reg = load_registry()
    
    if bot_key not in reg.get('BOTS', {}):
        return jsonify({"success": False, "error": "Bot not found in registry"}), 404
        
    bot_file = reg['BOTS'][bot_key]['file']
    log_file = reg['BOTS'][bot_key].get('log', f"{bot_key}_log.txt")
    bot_name = reg['BOTS'][bot_key].get('name', bot_key)
    
    # SECURITY: Sanitize filenames before passing them to the shell
    safe_bot_file = shlex.quote(bot_file)
    safe_log_file = shlex.quote(log_file)
    
    kill_cmd = f"pkill -f 'python3 -u {safe_bot_file}'"
    
    try:
        if action == 'stop':
            subprocess.run(kill_cmd, shell=True)
            logger.info(f"Admin manually stopped bot: {bot_name}")
            return jsonify({"success": True, "new_status": "Offline"})
            
        elif action == 'start':
            # Always kill ghost processes before spawning a new one
            subprocess.run(kill_cmd, shell=True) 
            
            start_cmd = f"nohup python3 -u {safe_bot_file} > {safe_log_file} 2>&1 &"
            subprocess.Popen(start_cmd, shell=True)
            
            logger.info(f"Admin manually started bot: {bot_name}")
            return jsonify({"success": True, "new_status": "Online"})
            
    except Exception as e:
        logger.error(f"Subprocess execution failed for {bot_key}: {e}")
        return jsonify({"success": False, "error": "Internal server error during execution"}), 500

# ==========================================
# SERVER ENTRY POINT
# ==========================================
if __name__ == '__main__':
    # Pull port from environment, fallback to 5000
    port = int(os.getenv('FLASK_PORT', 5000))
    
    # ONLY enable debug mode if explicitly set in the .env file
    is_debug = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    
    logger.info(f"Web Dashboard initializing on Port {port} (Debug: {is_debug})...")
    app.run(host='0.0.0.0', port=port, debug=is_debug)
