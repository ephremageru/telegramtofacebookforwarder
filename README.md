# Telegram → Facebook Forwarder — Master Orchestrator & Web CMS

[![Python Version](https://img.shields.io/badge/Python-3.10%2B-blue.svg)]()
[![Framework: Flask](https://img.shields.io/badge/Framework-Flask-black.svg)]()
[![Library: Telethon](https://img.shields.io/badge/Library-Telethon-lightgrey.svg)]()
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)]()

A production-oriented automation suite for scraping content from Telegram channels and forwarding it to Facebook Pages. The project provides two control surfaces — a Telegram Inline Keyboard "watchdog" for remote control of bot processes and a secure Web CMS (Flask) for configuration and monitoring.

Key design goals: reliability, secure remote management, robust media handling (single images, videos, and multi-photo albums), and simple deployment for scale.

---

## Table of contents

- [Repository structure](#repository-structure)
- [Architecture overview](#architecture-overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration (.env)](#configuration-env)
- [Running](#running)
- [Security notes](#security-notes)
- [Development & contribution](#development--contribution)
- [License](#license)

---

## Repository structure

| File / Dir | Purpose |
|------------|---------|
| `main.py`  | Bridge engine: listens to configured Telegram sources, formats media/text, batches albums, and posts to Facebook Pages using the Graph API. |
| `watchdog.py` | Master Telegram controller: provides an inline keyboard UI in Telegram to start/stop/pause/monitor child bot processes and receive alerts. |
| `app.py`   | Pro Web CMS (Flask): authentication-protected admin UI for viewing logs, start/stop processes, and editing configuration. |
| `web.py`   | Lightweight Web CMS: minimal dashboard useful for local/private deployments (no auth by default). |
| `templates/` | Frontend templates (dashboard, login) styled with Tailwind CSS. |
| `requirements.txt` | Python package dependencies. |
| `.env`     | (Not checked in) Environment variables and secrets. |

---

## Architecture overview

Text diagram:

```
[ Telegram Source Channels ] --(MTProto)-->
[ main.py (Bridge) ] --(Graph API v19.0)--> [ Facebook Page ]
          ▲
          |
    Reports / pings
          |
[ Web CMS (app.py) ] ←→ [ Admin User (Browser) ]
          ▲
          |
[ Telegram Watchdog (watchdog.py) ] ←→ [ Admin User (Telegram) ]
```

---

## Features

- Universal media forwarding: single photos, videos, and multi-photo albums are detected, downloaded, properly grouped, and forwarded to Facebook as coherent posts.
- Async processing & batching: uses asyncio to debounce and batch media into albums before upload.
- Pro Web CMS: secure admin login, live logs, process health checks, and dynamic configuration edits.
- Telegram watchdog: inline keyboard for remote process control and alerting.
- Shell-injection mitigations: command inputs from the web UI are sanitized using `shlex` and validated with regex.
- Auto-healing: background tasks monitor child processes and automatically restart crashed bots.

---

## Prerequisites

- Python 3.10 or later
- Unix-like host for production (Debian/Ubuntu recommended)
- Telegram API credentials (my.telegram.org)
- Telegram Bot token (from BotFather) for the watchdog
- Facebook Page ID and a Page Access Token with permissions to publish (Graph API)
- (Recommended) A process manager (systemd, supervisord) or Docker for production

---

## Installation

1. Clone this repository:

```bash
git clone https://github.com/ephremageru/telegramtofacebookforwarder.git
cd telegramtofacebookforwarder
```

2. Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate          # On Windows: venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## Configuration (.env)

Create a `.env` file in the project root with the values below. Keep this file private — never commit it.

Example `.env`:

```env
# Telegram (from https://my.telegram.org)
API_ID=your_api_id
API_HASH=your_api_hash

# Admin Watchdog (Telegram bot)
BOT_TOKEN=your_botfather_token
ADMIN_CHAT_ID=your_telegram_user_id

# Facebook (publish permissions)
FB_PAGE_ID=your_facebook_page_id
FB_PAGE_ACCESS_TOKEN=your_long_lived_page_access_token

# Web CMS
SECRET_KEY=your_super_secret_cookie_key
ADMIN_USERNAME=admin
ADMIN_PASSWORD=your_secure_password
FLASK_PORT=5000
FLASK_DEBUG=False
```

Important:
- Use a long-lived Facebook Page access token appropriate for server-side publishing.
- Limit ADMIN_PASSWORD complexity and consider using environment-based secrets or a secrets manager in production.

---

## Running

Examples for development and production usage.

1. Telegram watchdog (run in background):

```bash
# Development
python3 watchdog.py

# Production (example, using nohup)
nohup python3 watchdog.py > watchdog.log 2>&1 &
```

2. Web CMS (Flask) — development:

```bash
python3 app.py
# Visit: http://localhost:5000
```

3. Web CMS — production (example using Gunicorn):

```bash
nohup gunicorn --workers 2 --bind 0.0.0.0:5000 app:app &
```

4. Bridge (main) process:

```bash
# Run in foreground for testing
python3 main.py

# Production: use systemd or supervisor to run as a service (recommended)
```

Deployment tip: use a process manager (systemd, supervisord, or Docker + restart policy) to ensure auto-restart and controlled logs.

---

## Security notes

- Do NOT store tokens in version control. Use `.env` or a secrets manager.
- The Web CMS contains dynamic config editing features — restrict access (network-level + strong passwords).
- When exposing the web dashboard to the internet, use TLS (letsencrypt) and a reverse proxy (nginx).
- Facebook publishing requires appropriate permissions; ensure you follow Facebook Platform policies to avoid rate-limiting or app suspension.

---

## Development & contribution

- Fork the repo, create a feature branch, and open a pull request.
- Include tests for new behavior where possible.
- If you add new environment variables, update the README `.env` section.
- For security fixes or urgent changes, open an issue or a PR marked with high priority.

Suggested immediate improvements
- Add a `.env.example` template to the repo.
- Add systemd unit file examples and Dockerfiles for easier production deployment.
- Add unit/integration tests for media batch logic and Facebook upload flows.

---

## License

MIT — see LICENSE file.

---

Built by [ephremageru](https://github.com/ephremageru). Use responsibly and respect the terms of service of Telegram and Facebook.
