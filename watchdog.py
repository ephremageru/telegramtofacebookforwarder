import os
import time
import requests
import asyncio
import subprocess
import json
import re
import ast
import shutil
import random
import logging
from datetime import datetime
from dotenv import load_dotenv
from telethon import TelegramClient, events, Button

# ==========================================
# SYSTEM CONFIGURATION & LOGGING
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("WatchdogOrchestrator")

load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
BOT_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

# Web Dashboard (Default to localhost if not provided in .env)
WEB_DASHBOARD_URL = os.getenv('WEB_DASHBOARD_URL', 'http://127.0.0.1:5000')

if not all([API_ID, API_HASH, BOT_TOKEN, ADMIN_CHAT_ID]):
    raise ValueError("Missing critical environment variables. Please check your .env file.")

ADMIN_CHAT_ID = int(ADMIN_CHAT_ID)

PAUSED_FILE = 'paused_sources.json'
REGISTRY_FILE = 'watchdog_registry.json'

client = TelegramClient('watchdog_super_session', int(API_ID), API_HASH)
USER_STATE = {}
TEMP_NEW_PAGE = {}

# ==========================================
# REGISTRY & FILE MANAGEMENT
# ==========================================
def load_registry():
    if not os.path.exists(REGISTRY_FILE):
        return {"BOTS": {}, "FB_PAGES": {}}
    with open(REGISTRY_FILE, 'r') as f: 
        return json.load(f)

def save_registry(data):
    with open(REGISTRY_FILE, 'w') as f: 
        json.dump(data, f, indent=4)

def get_sources(bot_key):
    reg = load_registry()
    try:
        with open(reg['BOTS'][bot_key]['file'], 'r') as f: 
            content = f.read()
        match = re.search(r"SOURCE_CHANNELS\s*=\s*(\[.*?\])", content)
        if match: 
            return ast.literal_eval(match.group(1))
    except Exception as e: 
        logger.error(f"Failed to read sources for {bot_key}: {e}")
    return []

def modify_bot_file(bot_key, field, new_value):
    reg = load_registry()
    file_path = reg['BOTS'][bot_key]['file']
    try:
        with open(file_path, 'r') as f: 
            content = f.read()
            
        if field == 'sources':
            content = re.sub(r"SOURCE_CHANNELS\s*=\s*\[.*?\]", f"SOURCE_CHANNELS = {str(new_value)}", content)
        elif field == 'token':
            content = re.sub(r"FB_ACCESS_TOKEN\s*=\s*['\"].*?['\"]", f"FB_ACCESS_TOKEN = '{new_value}'", content)
        elif field == 'ig_id':
            content = re.sub(r"IG_(USER|ACCOUNT)_ID\s*=\s*['\"].*?['\"]", f"IG_\\1_ID = '{new_value}'", content)
        elif field == 'fb_id':
            content = re.sub(r"FB_PAGE_ID\s*=\s*['\"].*?['\"]", f"FB_PAGE_ID = '{new_value}'", content)
            
        with open(file_path, 'w') as f: 
            f.write(content)
            
        control_bot(bot_key, "start") 
        return True
    except Exception as e: 
        logger.error(f"Failed to modify bot file for {bot_key}: {e}")
        return False

def load_paused():
    if os.path.exists(PAUSED_FILE):
        with open(PAUSED_FILE, 'r') as f: 
            return json.load(f)
    return {}

def save_paused(data):
    with open(PAUSED_FILE, 'w') as f: 
        json.dump(data, f)

# ==========================================
# PROCESS CONTROL & KEYBOARDS
# ==========================================
def get_main_keyboard():
    reg = load_registry()
    buttons = [
        [Button.text("📊 Summary", resize=True), Button.text("▶️ Start All"), Button.text("🛑 Stop All")],
        [Button.text("🧹 Clean Logs"), Button.text("📄 All Logs"), Button.text("➕ Add New Page")],
        [Button.text("🌐 Web CMS Dashboard")]
    ]
    page_buttons = [Button.text(bot['name']) for key, bot in reg.get('BOTS', {}).items()]
    for i in range(0, len(page_buttons), 2):
        buttons.append(page_buttons[i:i+2])
    return buttons

def get_bot_inline_keyboard(bot_key):
    return [
        [Button.inline("▶️ Start", f"start_{bot_key}".encode()), Button.inline("🛑 Stop", f"stop_{bot_key}".encode()), Button.inline("🔄 Restart", f"restart_{bot_key}".encode())],
        [Button.inline("📡 Manage Sources", f"sources_{bot_key}".encode()), Button.inline("📈 Stats", f"stats_{bot_key}".encode())],
        [Button.inline("🔑 Edit FB Token", f"settoken_{bot_key}".encode()), Button.inline("📸 Edit IG ID", f"setig_{bot_key}".encode())],
        [Button.inline("🗑 Delete Page", f"delpage_{bot_key}".encode()), Button.inline("✍️ Post", f"newpost_{bot_key}".encode())]
    ]

def control_bot(bot_key, action):
    """Controls child processes via OS-level signals (Linux/Unix only)."""
    reg = load_registry()
    if bot_key not in reg['BOTS']: return
    
    bot_file = reg['BOTS'][bot_key]['file']
    log_file = reg['BOTS'][bot_key]['log']
    kill_cmd = f"pkill -f 'python3 -u {bot_file}'"
    
    if action == "stop": 
        subprocess.run(kill_cmd, shell=True)
    elif action == "start": 
        subprocess.run(kill_cmd, shell=True) 
        subprocess.Popen(f"nohup python3 -u {bot_file} > {log_file} 2>&1 &", shell=True)

# ==========================================
# TELEGRAM EVENT HANDLERS
# ==========================================
@client.on(events.NewMessage(chats=ADMIN_CHAT_ID))
async def main_menu_handler(event):
    text = event.raw_text
    reg = load_registry()
    
    if text == "📊 Summary": 
        try:
            output = subprocess.check_output("ps aux", shell=True).decode('utf-8')
            msg = "📊 **GLOBAL EMPIRE SUMMARY**\n\n"
            for key, bot in reg.get('BOTS', {}).items():
                icon = "🟢" if f"python3 -u {bot['file']}" in output else "🔴"
                msg += f"{icon} **{bot['name']}**\n"
            await event.reply(msg, buttons=get_main_keyboard())
        except Exception as e:
            await event.reply(f"⚠️ Error generating summary: {e}")

    elif text == "▶️ Start All":
        for key in reg.get('BOTS', {}): control_bot(key, "start")
        await event.reply("🚀 All bots started!", buttons=get_main_keyboard())
        
    elif text == "🛑 Stop All":
        for key in reg.get('BOTS', {}): control_bot(key, "stop")
        await event.reply("🛑 All bots stopped!", buttons=get_main_keyboard())
        
    elif text == "🧹 Clean Logs":
        for key in reg.get('BOTS', {}):
            if os.path.exists(reg['BOTS'][key]['log']): 
                open(reg['BOTS'][key]['log'], 'w').close()
        await event.reply("🧹 **All Log Files Cleaned!**", buttons=get_main_keyboard())
        
    elif text == "📄 All Logs":
        msg = "📄 **GLOBAL LIVE LOGS (Last 3 updates)**\n\n"
        for key, bot in reg.get('BOTS', {}).items():
            msg += f"**{bot['name']}**:\n"
            if os.path.exists(bot['log']):
                try:
                    tail = subprocess.check_output(f"tail -n 3 {bot['log']}", shell=True).decode('utf-8')
                    msg += f"`{tail.strip()}`\n\n"
                except: 
                    msg += "`No recent activity.`\n\n"
            else: 
                msg += "`Log file empty.`\n\n"
                
        if len(msg) > 4000: 
            msg = msg[:4000] + "\n...[MESSAGE TRUNCATED]"
        await event.reply(msg, buttons=get_main_keyboard())

    elif text == "🌐 Web CMS Dashboard":
        try:
            output = subprocess.check_output("ps aux", shell=True).decode('utf-8')
            is_running = "gunicorn" in output and "app:app" in output
            status = "🟢 **ONLINE**" if is_running else "🔴 **OFFLINE**"

            msg = f"🌐 **WEB CMS CONTROLLER**\n\n**Status:** {status}\n**Link:** `{WEB_DASHBOARD_URL}`\n\n*Manage your Flask web server below:*"
            buttons = [[Button.inline("▶️ Turn ON Server", b"web_start"), Button.inline("🛑 Turn OFF Server", b"web_stop")]]
            
            if is_running:
                buttons.append([Button.url("📱 Open Dashboard", WEB_DASHBOARD_URL)])

            await event.reply(msg, buttons=buttons)
        except Exception as e:
            await event.reply(f"⚠️ Error checking web status: {e}")
        
    elif text == "➕ Add New Page":
        USER_STATE[ADMIN_CHAT_ID] = "wizard_name"
        await event.reply("🛠 **NEW PAGE WIZARD**\n\n1️⃣ What is the **Name** of the new page? (e.g., 💻 Tech News)\n*(Type /cancel to abort)*")
        
    elif text in ["/start", "/menu", "/help"]: 
        await event.reply("🦸‍♂️ **Dashboard Online**", buttons=get_main_keyboard())
        
    elif text == "/cancel":
        USER_STATE.pop(ADMIN_CHAT_ID, None)
        TEMP_NEW_PAGE.pop(ADMIN_CHAT_ID, None)
        await event.reply("🚫 Action cancelled.")

    else:
        for key, bot_data in reg.get('BOTS', {}).items():
            if text == bot_data['name']:
                await event.reply(f"⚙️ **{bot_data['name']} Control Panel**", buttons=get_bot_inline_keyboard(key))
                return
                
        # --- WIZARD & STATE PROCESSING ---
        if ADMIN_CHAT_ID in USER_STATE:
            state_data = USER_STATE[ADMIN_CHAT_ID]
            message_text = event.message.message or ""
            
            if state_data == "wizard_name":
                TEMP_NEW_PAGE[ADMIN_CHAT_ID] = {"name": message_text}
                USER_STATE[ADMIN_CHAT_ID] = "wizard_fbid"
                await event.reply("2️⃣ What is the **Facebook Page ID**?")
                
            elif state_data == "wizard_fbid":
                TEMP_NEW_PAGE[ADMIN_CHAT_ID]["fb_id"] = message_text.strip()
                USER_STATE[ADMIN_CHAT_ID] = "wizard_token"
                await event.reply("3️⃣ Paste the **Facebook Access Token**:")
                
            elif state_data == "wizard_token":
                TEMP_NEW_PAGE[ADMIN_CHAT_ID]["token"] = message_text.strip()
                USER_STATE[ADMIN_CHAT_ID] = "wizard_source"
                await event.reply("4️⃣ What is the **Telegram Source Channel ID**?")

            elif state_data == "wizard_source":
                source_id = int(message_text.strip()) if message_text.strip().lstrip('-').isdigit() else message_text.strip()
                page_data = TEMP_NEW_PAGE[ADMIN_CHAT_ID]
                key_name = re.sub(r'[^a-zA-Z0-9]', '', page_data['name']).lower()
                
                if key_name in reg.get('BOTS', {}): 
                    key_name += str(random.randint(10,99))
                
                bot_filename = f"{key_name}_bot.py"
                
                # NOTE: Requires a 'bot.py' template file in the root directory!
                if os.path.exists("bot.py"): 
                    shutil.copy("bot.py", bot_filename)
                else:
                    await event.reply("❌ Error: `bot.py` template file not found.")
                    USER_STATE.pop(ADMIN_CHAT_ID, None)
                    return

                reg['BOTS'][key_name] = {"file": bot_filename, "log": f"{key_name}_log.txt", "name": page_data['name']}
                reg['FB_PAGES'][key_name] = {"id": page_data['fb_id'], "token": page_data['token'], "ig_id": ""}
                
                save_registry(reg)
                modify_bot_file(key_name, "sources", [source_id])
                modify_bot_file(key_name, "token", page_data['token'])
                modify_bot_file(key_name, "fb_id", page_data['fb_id'])
                
                USER_STATE.pop(ADMIN_CHAT_ID, None)
                TEMP_NEW_PAGE.pop(ADMIN_CHAT_ID, None)
                await event.reply(f"✅ **{page_data['name']}** dynamically deployed!", buttons=get_main_keyboard())

            elif state_data.startswith("addsrc_"):
                bot_key = state_data.split("_")[1]
                new_src = message_text.strip()
                if new_src.lstrip('-').isdigit(): new_src = int(new_src)
                
                current_sources = get_sources(bot_key)
                if new_src not in current_sources:
                    current_sources.append(new_src)
                    if modify_bot_file(bot_key, "sources", current_sources):
                        await event.reply(f"✅ Added `{new_src}` and restarted the bot!")
                    else: 
                        await event.reply("❌ Failed to update the .py file.")
                else: 
                    await event.reply("⚠️ Source already exists.")
                USER_STATE.pop(ADMIN_CHAT_ID, None)

            elif state_data.startswith("inputtoken_"):
                bot_key = state_data.split("_")[1]
                new_token = message_text.strip()
                reg['FB_PAGES'][bot_key]['token'] = new_token
                save_registry(reg)
                
                if modify_bot_file(bot_key, "token", new_token):
                    await event.reply(f"✅ New Access Token injected!")
                else: 
                    await event.reply("❌ Failed to update the .py file.")
                USER_STATE.pop(ADMIN_CHAT_ID, None)

            elif state_data.startswith("inputig_"):
                bot_key = state_data.split("_")[1]
                new_ig = message_text.strip()
                reg['FB_PAGES'][bot_key]['ig_id'] = new_ig
                save_registry(reg)
                
                if modify_bot_file(bot_key, "ig_id", new_ig):
                    await event.reply(f"📸 New Instagram ID injected!")
                else: 
                    await event.reply("❌ Failed to update the .py file.")
                USER_STATE.pop(ADMIN_CHAT_ID, None)

            elif state_data.startswith("newpost_"):
                bot_key = state_data.split("_")[1]
                page_token = reg['FB_PAGES'][bot_key]['token']
                fb_id = reg['FB_PAGES'][bot_key]['id']
                await event.reply(f"📤 Uploading to **{reg['BOTS'][bot_key]['name']}**...")
                
                try:
                    if bool(event.message.media) and hasattr(event.message.media, 'photo'):
                        if not os.path.exists("downloads"): os.makedirs("downloads")
                        media_path = await event.message.download_media(file="downloads/")
                        res = requests.post(
                            f"https://graph.facebook.com/v19.0/{fb_id}/photos", 
                            data={'message': message_text, 'published': 'true', 'access_token': page_token}, 
                            files={'source': open(media_path, 'rb')}
                        ).json()
                        os.remove(media_path)
                    else:
                        res = requests.post(
                            f"https://graph.facebook.com/v19.0/{fb_id}/feed", 
                            data={'message': message_text, 'access_token': page_token}
                        ).json()
                    
                    if 'id' in res or 'post_id' in res: 
                        await event.reply("✅ **SUCCESS! IT IS LIVE!**")
                    else: 
                        await event.reply(f"❌ **FAILED:**\n`{res}`")
                except Exception as e: 
                    await event.reply(f"⚠️ **Error:** {e}")
                USER_STATE.pop(ADMIN_CHAT_ID, None)

            elif state_data.startswith("edittext_"):
                parts = state_data.split("_")
                bot_key, post_id = parts[1], parts[2]
                page_token = reg['FB_PAGES'][bot_key]['token']
                res = requests.post(
                    f"https://graph.facebook.com/v19.0/{post_id}", 
                    data={'message': message_text, 'access_token': page_token}
                ).json()
                
                if res.get('success') or 'id' in res: 
                    await event.reply("✅ **Post Updated!**")
                else: 
                    await event.reply(f"❌ **Failed to edit post:** {res}")
                USER_STATE.pop(ADMIN_CHAT_ID, None)

# ==========================================
# INLINE CALLBACK HANDLERS
# ==========================================
@client.on(events.CallbackQuery())
async def callback_handler(event):
    data = event.data.decode('utf-8')
    reg = load_registry()

    # Web CMS Execution
    if data == "web_start":
        subprocess.run("pkill -f gunicorn", shell=True)
        subprocess.Popen("nohup gunicorn --workers 1 --bind 0.0.0.0:5000 app:app > cms_log.txt 2>&1 &", shell=True)
        await event.edit("✅ **Web CMS Starting!**\nGive it 5 seconds to boot up.")
        return
        
    elif data == "web_stop":
        subprocess.run("pkill -f gunicorn", shell=True)
        await event.edit("🛑 **Web CMS Stopped.**\nThe website is now offline and secure.")
        return

    parts = data.split("_")
    action = parts[0]
    bot_key = parts[1] if len(parts) > 1 else ""

    if action == "sources":
        sources = get_sources(bot_key)
        paused = load_paused().get(bot_key, {})
        msg = f"📡 **Sources for {reg['BOTS'][bot_key]['name']}**\n\n**Active:**\n"
        for i, src in enumerate(sources): 
            msg += f"{i+1}. `{src}`\n"
            
        if paused:
            msg += "\n**⏸ Paused:**\n"
            for src, res_time in paused.items(): 
                msg += f"• `{src}` *(Resumes in {round((res_time - time.time()) / 3600, 1)}h)*\n"
                
        buttons = [
            [Button.inline("➕ Add Source", f"addsrc_{bot_key}".encode()), Button.inline("➖ Remove Source", f"remsrc_{bot_key}".encode())],
            [Button.inline("⏸ Pause a Source", f"pausesrc_{bot_key}".encode())]
        ]
        await event.reply(msg, buttons=buttons)

    elif action == "addsrc":
        USER_STATE[event.chat_id] = f"addsrc_{bot_key}"
        await event.reply(f"➕ **Send channel username/ID to add to {reg['BOTS'][bot_key]['name']}.**")

    elif action == "remsrc":
        sources = get_sources(bot_key)
        buttons = [[Button.inline(f"❌ {src}", f"delsrc_{bot_key}_{i}".encode())] for i, src in enumerate(sources)]
        await event.reply("➖ **Click a source below to permanently remove it:**", buttons=buttons)

    elif action == "pausesrc":
        sources = get_sources(bot_key)
        buttons = [[Button.inline(f"⏸ {src}", f"pickpause_{bot_key}_{i}".encode())] for i, src in enumerate(sources)]
        await event.reply("⏸ **Click a source to temporarily pause it:**", buttons=buttons)

    elif action == "pickpause":
        index = int(parts[2])
        sources = get_sources(bot_key)
        if index < len(sources):
            src = sources[index]
            buttons = [
                [Button.inline("12 Hours", f"dopause_{bot_key}_{index}_12".encode()), 
                 Button.inline("24 Hours", f"dopause_{bot_key}_{index}_24".encode())]
            ]
            await event.reply(f"⏸ **Pause `{src}` for how long?**", buttons=buttons)

    elif action == "dopause":
        index, hours = int(parts[2]), int(parts[3])
        sources = get_sources(bot_key)
        if index < len(sources):
            src = sources.pop(index)
            if modify_bot_file(bot_key, "sources", sources):
                paused_data = load_paused()
                if bot_key not in paused_data: 
                    paused_data[bot_key] = {}
                paused_data[bot_key][str(src)] = time.time() + (hours * 3600)
                save_paused(paused_data)
                await event.edit(f"✅ Paused `{src}` for {hours} hours.")

    elif action == "delsrc":
        index = int(parts[2])
        sources = get_sources(bot_key)
        if index < len(sources):
            removed = sources.pop(index)
            if modify_bot_file(bot_key, "sources", sources): 
                await event.edit(f"🗑 Removed `{removed}` and restarted bot!")

    elif action in ["start", "stop", "restart"]:
        control_bot(bot_key, "start" if action != "stop" else "stop")
        await event.answer(f"{action.capitalize()}ed process!", alert=True)

    elif action == "logs":
        try:
            tail = subprocess.check_output(f"tail -n 15 {reg['BOTS'][bot_key]['log']}", shell=True).decode('utf-8')
            await event.reply(f"📋 **Logs:**\n`{tail}`")
        except: 
            await event.reply("⚠️ Error reading logs.")
        
    elif action == "stats":
        try:
            succ, err, lines = 0, 0, 0
            with open(reg['BOTS'][bot_key]['log'], 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    lines += 1
                    if "[SUCCESS]" in line or "Successfully" in line: succ += 1
                    if "[ERROR]" in line or "Failed" in line: err += 1
            await event.reply(f"📈 **Analytics**\n✅ Success: {succ}\n❌ Errors: {err}\n📄 Total Logs: {lines}")
        except: 
            await event.reply("⚠️ Error reading analytics.")
        
    elif action == "newpost":
        USER_STATE[event.chat_id] = f"newpost_{bot_key}"
        await event.reply(f"✍️ **Drafting new post... Send media or text:**")

    elif action == "settoken":
        USER_STATE[event.chat_id] = f"inputtoken_{bot_key}"
        await event.reply(f"🔑 **Change Token for {reg['BOTS'][bot_key]['name']}**\nPaste the new EAANwS... token below:\n*(Type /cancel to abort)*")
        
    elif action == "setig":
        USER_STATE[event.chat_id] = f"inputig_{bot_key}"
        await event.reply(f"📸 **Change IG ID for {reg['BOTS'][bot_key]['name']}**\nPaste the 17-digit Instagram ID below:\n*(Type /cancel to abort)*")

    elif action == "delpage":
        bot_name = reg['BOTS'][bot_key]['name']
        control_bot(bot_key, "stop") 
        del reg['BOTS'][bot_key]
        del reg['FB_PAGES'][bot_key]
        save_registry(reg)
        await event.edit(f"🗑 **{bot_name}** has been stopped and deleted from the dashboard.", buttons=get_main_keyboard())

    elif action == "delpost":
        post_id = parts[2]
        page_token = reg['FB_PAGES'][bot_key]['token']
        res = requests.delete(f"https://graph.facebook.com/v19.0/{post_id}", params={'access_token': page_token}).json()
        if res.get('success'): 
            await event.edit("🗑 **POST DELETED FROM FACEBOOK!**")
        else: 
            await event.answer(f"Failed: {res}", alert=True)

    elif action == "editpost":
        post_id = parts[2]
        USER_STATE[event.chat_id] = f"edittext_{bot_key}_{post_id}"
        await event.reply(f"✏️ **Edit Post**\n\nSend the new text for this post below:\n*(Type /cancel to abort)*")

# ==========================================
# ASYNC BACKGROUND TASKS
# ==========================================
async def smart_health_monitor():
    """Checks every hour if tracked processes have crashed, auto-restarts if needed."""
    while True:
        await asyncio.sleep(3600)
        reg = load_registry()
        try:
            output = subprocess.check_output("ps aux", shell=True).decode('utf-8')
            for key, bot in reg.get('BOTS', {}).items():
                if f"python3 -u {bot['file']}" not in output:
                    await client.send_message(ADMIN_CHAT_ID, f"🔔 **CRASH ALERT:** `{bot['name']}` is offline! Auto-restarting...")
                    control_bot(key, "start")
        except Exception as e: 
            logger.error(f"Health monitor error: {e}")

async def auto_unpauser():
    """Routinely checks paused sources and injects them back into active scripts when time expires."""
    while True:
        await asyncio.sleep(60)
        paused_data = load_paused()
        reg = load_registry()
        changed = False
        current_time = time.time()
        
        for bot_key, channels in list(paused_data.items()):
            if bot_key not in reg.get('BOTS', {}): continue
            
            for src, resume_time in list(channels.items()):
                if current_time >= resume_time:
                    src_val = int(src) if src.lstrip('-').isdigit() else src
                    sources = get_sources(bot_key)
                    
                    if src_val not in sources:
                        sources.append(src_val)
                        modify_bot_file(bot_key, "sources", sources)
                        
                    del paused_data[bot_key][src]
                    changed = True
                    try: 
                        await client.send_message(ADMIN_CHAT_ID, f"▶️ **AUTO-UNPAUSE:** `{src}` reactivated for {reg['BOTS'][bot_key]['name']}!")
                    except: 
                        pass
                        
            if not paused_data[bot_key]: 
                del paused_data[bot_key]
                
        if changed: 
            save_paused(paused_data)

async def auto_restarter():
    """Restarts all child processes every 12 hours to prevent memory leaks."""
    while True:
        await asyncio.sleep(43200)
        reg = load_registry()
        for key in reg.get('BOTS', {}): 
            control_bot(key, "start")
        try: 
            await client.send_message(ADMIN_CHAT_ID, "🔄 **SYSTEM AUTO-MAINTENANCE:** All bots restarted to clear memory leaks.")
        except: 
            pass

if __name__ == '__main__':
    logger.info("🦸‍♂️ Superman Watchdog Engine is initializing...")
    load_registry() 
    
    client.start(bot_token=BOT_TOKEN)
    logger.info("Telegram Client Authenticated.")
    
    client.loop.create_task(auto_restarter())
    client.loop.create_task(auto_unpauser())
    client.loop.create_task(smart_health_monitor())
    
    logger.info("Event loop running. Press Ctrl+C to stop.")
    client.run_until_disconnected()
