import os
import json
import subprocess
import shutil
import re
import ast
import random
import logging
import shlex
from functools import wraps
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from dotenv import load_dotenv

# ==========================================
# SYSTEM CONFIGURATION & LOGGING
# ==========================================
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("EmpireCMS")

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', os.urandom(24))

ADMIN_USERNAME = os.getenv('ADMIN_USERNAME')
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD')
REGISTRY_FILE = os.getenv('REGISTRY_FILE', 'watchdog_registry.json')

if not ADMIN_USERNAME or not ADMIN_PASSWORD:
    logger.warning("Admin credentials are not set in the .env file! Login will fail.")

# ==========================================
# HELPER FUNCTIONS
# ==========================================
def load_json(filepath, default):
    if not os.path.exists(filepath): 
        return default
    try:
        with open(filepath, 'r') as f: 
            return json.load(f)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse {filepath}: {e}")
        return default

def save_json(filepath, data):
    try:
        with open(filepath, 'w') as f: 
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Failed to save {filepath}: {e}")

def sanitize_filename(filename):
    """Prevents Shell Injection by stripping dangerous characters."""
    return re.sub(r'[^a-zA-Z0-9_.]', '', filename)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "error": "Unauthorized"}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# ==========================================
# FILE MODIFIERS (REGEX)
# ==========================================
def get_bot_config_from_file(bot_key):
    reg = load_json(REGISTRY_FILE, {"BOTS": {}})
    if bot_key not in reg['BOTS']: 
        return {}
    
    file_path = reg['BOTS'][bot_key]['file']
    config = {"sources": [], "token": "", "ig_id": "", "fb_id": ""}
    
    if not os.path.exists(file_path):
        return config

    try:
        with open(file_path, 'r') as f: 
            content = f.read()
            
        src_match = re.search(r"SOURCE_CHANNELS\s*=\s*(\[.*?\])", content)
        if src_match: config["sources"] = ast.literal_eval(src_match.group(1))
        
        tok_match = re.search(r"FB_ACCESS_TOKEN\s*=\s*['\"](.*?)['\"]", content)
        if tok_match: config["token"] = tok_match.group(1)
        
        ig_match = re.search(r"IG_(USER|ACCOUNT)_ID\s*=\s*['\"](.*?)['\"]", content)
        if ig_match: config["ig_id"] = ig_match.group(2)
        
        fb_match = re.search(r"FB_PAGE_ID\s*=\s*['\"](.*?)['\"]", content)
        if fb_match: config["fb_id"] = fb_match.group(1)
    except Exception as e: 
        logger.error(f"Error parsing config for {bot_key}: {e}")
        
    return config

def modify_bot_file(bot_key, sources=None, token=None, ig_id=None, fb_id=None):
    reg = load_json(REGISTRY_FILE, {"BOTS": {}})
    if bot_key not in reg['BOTS']: return False
    
    file_path = reg['BOTS'][bot_key]['file']
    try:
        with open(file_path, 'r') as f: 
            content = f.read()
            
        if sources is not None:
            content = re.sub(r"SOURCE_CHANNELS\s*=\s*\[.*?\]", f"SOURCE_CHANNELS = {str(sources)}", content)
        if token is not None:
            content = re.sub(r"FB_ACCESS_TOKEN\s*=\s*['\"].*?['\"]", f"FB_ACCESS_TOKEN = '{token}'", content)
        if ig_id is not None:
            content = re.sub(r"IG_(USER|ACCOUNT)_ID\s*=\s*['\"].*?['\"]", f"IG_\\1_ID = '{ig_id}'", content)
        if fb_id is not None:
            content = re.sub(r"FB_PAGE_ID\s*=\s*['\"].*?['\"]", f"FB_PAGE_ID = '{fb_id}'", content)
            
        with open(file_path, 'w') as f: 
            f.write(content)
        return True
    except Exception as e: 
        logger.error(f"Error modifying file for {bot_key}: {e}")
        return False

# ==========================================
# WEB UI ROUTES
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if request.form.get('username') == ADMIN_USERNAME and request.form.get('password') == ADMIN_PASSWORD:
            session['logged_in'] = True
            logger.info("Successful admin login.")
            return redirect(url_for('dashboard'))
        logger.warning(f"Failed login attempt from IP: {request.remote_addr}")
        return render_template('login.html', error="Invalid credentials")
    return render_template('login.html', error=None)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def dashboard():
    return render_template('index.html')

# ==========================================
# API ROUTES
# ==========================================
@app.route('/api/status', methods=['GET'])
@login_required
def get_status():
    reg = load_json(REGISTRY_FILE, {"BOTS": {}})
    status_data = {}
    
    try:
        output = subprocess.check_output("ps aux", shell=True).decode('utf-8')
    except Exception as e:
        logger.error(f"Failed to read processes: {e}")
        output = ""

    for key, bot in reg.get('BOTS', {}).items():
        safe_file = sanitize_filename(bot['file'])
        is_online = f"python3 -u {safe_file}" in output
        
        succ, err = 0, 0
        if os.path.exists(bot['log']):
            try:
                with open(bot['log'], 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                    succ = content.count("[SUCCESS]")
                    err = content.count("[ERROR]")
            except Exception as e: 
                logger.error(f"Error reading log for {key}: {e}")
            
        status_data[key] = {
            "name": bot['name'], 
            "file": bot['file'], 
            "status": "Online" if is_online else "Offline", 
            "success": succ, 
            "error": err
        }
    return jsonify({"success": True, "bots": status_data})

@app.route('/api/toggle/<bot_key>', methods=['POST'])
@login_required
def toggle_bot(bot_key):
    action = request.json.get('action')
    reg = load_json(REGISTRY_FILE, {"BOTS": {}})
    
    if bot_key not in reg['BOTS']: 
        return jsonify({"success": False, "error": "Bot not found"})
        
    bot_file = sanitize_filename(reg['BOTS'][bot_key]['file'])
    log_file = sanitize_filename(reg['BOTS'][bot_key]['log'])
    
    kill_cmd = f"pkill -f 'python3 -u {bot_file}'"

    try:
        if action in ['stop', 'restart']:
            subprocess.run(kill_cmd, shell=True)
            if action == 'stop': 
                return jsonify({"success": True, "status": "Offline"})

        if action in ['start', 'restart']:
            subprocess.run(kill_cmd, shell=True)
            subprocess.Popen(f"nohup python3 -u {bot_file} > {log_file} 2>&1 &", shell=True)
            return jsonify({"success": True, "status": "Online"})
            
    except Exception as e:
        logger.error(f"Process control failed for {bot_key}: {e}")
        return jsonify({"success": False, "error": "Server error controlling process"})

@app.route('/api/config/<bot_key>', methods=['GET', 'POST'])
@login_required
def manage_config(bot_key):
    if request.method == 'GET':
        return jsonify({"success": True, "config": get_bot_config_from_file(bot_key)})
    
    if request.method == 'POST':
        data = request.json
        sources_raw = data.get('sources', '')
        parsed_sources = []
        for s in sources_raw.split(','):
            s = s.strip()
            if s: parsed_sources.append(int(s) if s.lstrip('-').isdigit() else s)
            
        success = modify_bot_file(bot_key, sources=parsed_sources, token=data.get('token'), ig_id=data.get('ig_id'))
        
        if success:
            # Auto restart to apply changes
            reg = load_json(REGISTRY_FILE, {"BOTS": {}})
            bot_file = sanitize_filename(reg['BOTS'][bot_key]['file'])
            log_file = sanitize_filename(reg['BOTS'][bot_key]['log'])
            subprocess.run(f"pkill -f 'python3 -u {bot_file}'", shell=True)
            subprocess.Popen(f"nohup python3 -u {bot_file} > {log_file} 2>&1 &", shell=True)
            return jsonify({"success": True})
            
        return jsonify({"success": False, "error": "Failed to update configuration"})

@app.route('/api/logs/<bot_key>', methods=['GET'])
@login_required
def get_logs(bot_key):
    reg = load_json(REGISTRY_FILE, {"BOTS": {}})
    if bot_key not in reg['BOTS']: 
        return jsonify({"success": False, "error": "Bot not found"})
    
    log_file = reg['BOTS'][bot_key]['log']
    if not os.path.exists(log_file): 
        return jsonify({"success": True, "logs": "No logs found yet."})
    
    try:
        with open(log_file, 'r', encoding='utf-8', errors='ignore') as f: 
            lines = f.readlines()[-30:]
        return jsonify({"success": True, "logs": "".join(lines)})
    except Exception as e:
        logger.error(f"Error serving logs for {bot_key}: {e}")
        return jsonify({"success": False, "error": "Could not read logs"})

@app.route('/api/add_bot', methods=['POST'])
@login_required
def add_bot():
    data = request.json
    name = data.get('name')
    fb_id = data.get('fb_id')
    token = data.get('token')
    
    if not all([name, fb_id, token]): 
        return jsonify({"success": False, "error": "Missing fields"})
        
    key_name = re.sub(r'[^a-zA-Z0-9]', '', name).lower()
    reg = load_json(REGISTRY_FILE, {"BOTS": {}, "FB_PAGES": {}})
    
    if key_name in reg['BOTS']: 
        key_name += str(random.randint(10,99))
        
    bot_filename = f"{key_name}_bot.py"
    log_filename = f"{key_name}_log.txt"
    
    if os.path.exists("bot.py"): 
        shutil.copy("bot.py", bot_filename)
    else: 
        return jsonify({"success": False, "error": "Template bot.py not found on server"})

    reg['BOTS'][key_name] = {"file": bot_filename, "log": log_filename, "name": name}
    reg['FB_PAGES'][key_name] = {"id": fb_id, "token": token, "ig_id": ""}
    save_json(REGISTRY_FILE, reg)
    
    modify_bot_file(key_name, token=token, fb_id=fb_id)
    
    return jsonify({"success": True})

@app.route('/api/delete_bot/<bot_key>', methods=['POST'])
@login_required
def delete_bot(bot_key):
    reg = load_json(REGISTRY_FILE, {"BOTS": {}, "FB_PAGES": {}})
    
    if bot_key not in reg['BOTS']: 
        return jsonify({"success": False, "error": "Bot not found"})
        
    bot_file = sanitize_filename(reg['BOTS'][bot_key]['file'])
    subprocess.run(f"pkill -f 'python3 -u {bot_file}'", shell=True)
        
    del reg['BOTS'][bot_key]
    if bot_key in reg.get('FB_PAGES', {}): 
        del reg['FB_PAGES'][bot_key]
        
    save_json(REGISTRY_FILE, reg)
    return jsonify({"success": True})

# ==========================================
# ENTRY POINT
# ==========================================
if __name__ == '__main__':
    port = int(os.getenv('FLASK_PORT', 5000))
    is_debug = os.getenv('FLASK_DEBUG', 'False').lower() in ['true', '1', 'yes']
    
    logger.info(f"🦸‍♂️ Starting Pro Empire CMS Web Server on port {port}...")
    app.run(host='0.0.0.0', port=port, debug=is_debug)
