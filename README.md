# 👑 13-Bot Empire: Master Orchestrator & Web CMS

![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)
![Flask](https://img.shields.io/badge/Framework-Flask-black.svg)
![Telethon](https://img.shields.io/badge/Library-Telethon-lightgrey.svg)
![License](https://img.shields.io/badge/License-MIT-green.svg)

Welcome to the **13-Bot Empire** repository! This project is a complete, production-grade automation suite designed for mass Telegram channel management, content scraping, and cross-platform publishing (Telegram to Facebook Graph API). 

It features a dual-control architecture: you can manage your fleet of bots directly via a **Telegram Inline Keyboard UI** or through a secure, fully authenticated **Web CMS Dashboard**.

---

## 📂 Repository Structure

Here is a breakdown of what each file in this repository does:

| File | Description |
|------|-------------|
| `main.py` | **The Bridge Engine:** Scrapes media and text from target Telegram channels, formats the content, batches albums together asynchronously, and auto-posts to Facebook Pages. |
| `watchdog.py` | **The Master Telegram Controller:** Generates an inline UI inside Telegram to remotely start, stop, pause, and monitor your fleet of child bots. |
| `app.py` | **Pro Web CMS (Recommended):** A highly secure Flask backend featuring admin login (`@login_required`), dynamic `.py` configuration editing, and log monitoring. |
| `web.py` | **Lightweight Web CMS:** A stripped-down, fast version of the web dashboard without authentication (useful for local/private network hosting). |
| `templates/` | Contains the frontend UI files (`index.html` for the dashboard, `login.html` for secure access) styled with Tailwind CSS. |
| `requirements.txt` | Contains all necessary Python dependencies (`Telethon`, `Flask`, `requests`, etc.). |
| `.env` | *(Not uploaded)* Your secure configuration file for storing API keys, passwords, and tokens. |

---

## 🏗️ System Architecture

```text
[ Telegram Source Channels ]
       │
       ▼ (Listened to by MTProto)
[ main.py (Facebook Bridge) ] ───► Formats, downloads, and groups media albums
       │
       ▼ (Uses Graph API v19.0)
[ Facebook Page ] ───► Sends success ping back to Admin Dashboard
````

```text
[ Admin User ]
       │
       ├─► Telegram App ──► [ watchdog.py ] (Process Management & Alerts)
       │
       └─► Web Browser  ──► [ app.py ] (Flask CMS: Start/Stop/Edit Configs)
```

-----

## ✨ Key Features

  * **Universal Media Forwarding:** Automatically downloads single photos, videos, and complex multi-photo albums from Telegram, debounces them using `asyncio`, and pushes them to Facebook as cohesive albums.
  * **Pro Web CMS Dashboard:** A beautiful, dark-mode Tailwind CSS dashboard to monitor process health (`ps aux`), read live logs, and dynamically modify bot source targets without opening a code editor.
  * **Shell-Injection Security:** The Flask backend utilizes `shlex` and regex sanitization to ensure malicious actors cannot pass terminal commands through the web UI.
  * **Auto-Healing:** Background asynchronous tasks monitor child processes every hour and auto-restart any bots that crash due to server memory leaks or network drops.

-----

## 🚀 Installation & Setup

**1. Clone the repository:**

```bash
git clone [https://github.com/ephremageru/13-Bot-Empire.git](https://github.com/ephremageru/13-Bot-Empire.git)
cd 13-Bot-Empire
```

**2. Set up your Virtual Environment & Install Dependencies:**

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
```

**3. Configure your Environment Variables:**
Create a file named `.env` in the root folder and add your credentials:

```env
# Telegram App Credentials (from my.telegram.org)
API_ID=your_api_id
API_HASH=your_api_hash

# Admin Watchdog Bot
BOT_TOKEN=your_botfather_token
ADMIN_CHAT_ID=your_telegram_user_id

# Web CMS Configuration
SECRET_KEY=your_super_secret_cookie_key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
FLASK_PORT=5000
FLASK_DEBUG=False
```

-----

## ▶️ Running the Empire

**Option 1: Start the Telegram Watchdog**
This brings your Telegram-based Inline Keyboard dashboard online.

```bash
nohup python3 watchdog.py &
```

**Option 2: Start the Web CMS Dashboard**
This brings the web interface online at `http://your-server-ip:5000`.

```bash
nohup gunicorn --workers 1 --bind 0.0.0.0:5000 app:app &
```

*(Note: If you just want to run the script directly for testing, you can use `python3 app.py`).*

**Option 3: Start the Facebook Bridge manually**

```bash
python3 main.py



*Built by [ephremageru](https://www.google.com/search?q=https://github.com/ephremageru). Designed for scale.*

```
```
