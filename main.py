import os
import time
import requests
import re
import asyncio
import json
import logging
from dotenv import load_dotenv
from telethon import TelegramClient, events

# Configure professional logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TgFbBridge")

# Load environment variables
load_dotenv()

API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
SESSION_NAME = 'tg_to_fb_session'

# ==========================================
# 🎯 USER CONFIGURATION
# ==========================================
# Add the Telegram channels you want to scrape from here.
SOURCE_CHANNELS = ['@PutYourSourceHere1', '@PutYourSourceHere2'] # <-- PUT SOURCES HERE

# Add the default hashtags you want appended to every Facebook post.
HASHTAGS = "\n\n#YourHashtag1 #YourHashtag2" # <-- PUT HASHTAGS HERE
# ==========================================

FB_PAGE_ID = os.getenv('FB_PAGE_ID')
FB_ACCESS_TOKEN = os.getenv('FB_ACCESS_TOKEN')
FB_GRAPH_URL = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}"

# Watchdog Connection Info
BOT_TOKEN = os.getenv('BOT_TOKEN')
YOUR_CHAT_ID = os.getenv('ADMIN_CHAT_ID')

if not all([API_ID, API_HASH, FB_PAGE_ID, FB_ACCESS_TOKEN, BOT_TOKEN, YOUR_CHAT_ID]):
    raise ValueError("Missing critical environment variables. Check your .env file.")

client = TelegramClient(SESSION_NAME, int(API_ID), API_HASH)

# In-memory cache for grouping media albums
ALBUM_CACHE = {}

def send_dashboard_alert(caption, media_paths, media_type, post_id):
    """Pings the Telegram admin dashboard with FB post details and action buttons."""
    actual_post_id = post_id.split('_')[-1] if '_' in post_id else post_id
    
    reply_markup = json.dumps({
        "inline_keyboard": [
            [
                {"text": "✏️ Edit FB Post", "callback_data": f"editpost_{actual_post_id}"},
                {"text": "🗑 Delete FB Post", "callback_data": f"delpost_{actual_post_id}"}
            ]
        ]
    })
    
    safe_caption = caption[:1000] + "..." if len(caption) > 1000 else caption
    first_media = media_paths[0] if media_paths else None
    
    try:
        if first_media and os.path.exists(first_media):
            if media_type == 'video':
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendVideo"
                with open(first_media, 'rb') as f:
                    requests.post(url, data={"chat_id": YOUR_CHAT_ID, "caption": safe_caption, "reply_markup": reply_markup}, files={"video": f})
            else:
                url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
                with open(first_media, 'rb') as f:
                    requests.post(url, data={"chat_id": YOUR_CHAT_ID, "caption": safe_caption, "reply_markup": reply_markup}, files={"photo": f})
        else:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
            requests.post(url, data={"chat_id": YOUR_CHAT_ID, "text": safe_caption, "reply_markup": reply_markup})
    except Exception as e:
        logger.error(f"Failed to send dashboard alert: {e}")

def post_to_facebook(text, media_paths=None, media_type=None):
    """Handles routing to the correct Facebook Graph API endpoint based on media type."""
    try:
        response = {}
        
        # 1. Text Only
        if not media_paths:
            url = f"{FB_GRAPH_URL}/feed"
            payload = {'message': text, 'access_token': FB_ACCESS_TOKEN}
            response = requests.post(url, data=payload).json()

        # 2. Single Media
        elif len(media_paths) == 1:
            media_path = media_paths[0]
            if media_type == 'video':
                url = f"{FB_GRAPH_URL}/videos"
                payload = {'description': text, 'access_token': FB_ACCESS_TOKEN}
                with open(media_path, 'rb') as vid:
                    response = requests.post(url, data=payload, files={'source': vid}).json()
            else:
                url = f"{FB_GRAPH_URL}/photos"
                payload = {'message': text, 'published': 'true', 'access_token': FB_ACCESS_TOKEN}
                with open(media_path, 'rb') as img:
                    response = requests.post(url, data=payload, files={'source': img}).json()
                    
        # 3. Album (Multiple Pictures)
        else:
            attached_media = []
            logger.info(f"Batch uploading {len(media_paths)} photos to Facebook...")
            
            # Step A: Upload hidden to generate IDs
            for path in media_paths:
                url = f"{FB_GRAPH_URL}/photos"
                payload = {'published': 'false', 'access_token': FB_ACCESS_TOKEN}
                with open(path, 'rb') as img:
                    res = requests.post(url, data=payload, files={'source': img}).json()
                    if 'id' in res:
                        attached_media.append({"media_fbid": res['id']})
            
            # Step B: Attach IDs to a single feed post
            feed_url = f"{FB_GRAPH_URL}/feed"
            feed_payload = {'message': text, 'access_token': FB_ACCESS_TOKEN}
            for i, media in enumerate(attached_media):
                feed_payload[f'attached_media[{i}]'] = json.dumps(media)
                
            response = requests.post(feed_url, data=feed_payload).json()

        # Process Result
        post_id = response.get('id') or response.get('post_id')
        if post_id:
            logger.info(f"Successfully posted to Facebook Graph API. ID: {post_id}")
            actual_id = post_id.split('_')[-1] if '_' in post_id else post_id
            caption = f"🚀 **AUTO-POST SUCCESS**\n\n{text}\n\n🔗 [View on Facebook](https://www.facebook.com/{FB_PAGE_ID}/posts/{actual_id})"
            send_dashboard_alert(caption, media_paths, media_type, post_id)
        else:
            logger.error(f"Facebook Graph API Error: {response}")
                
    except Exception as e:
        logger.error(f"Facebook connection failure: {e}")

@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handler(event):
    message_text = event.message.message or ""
    chat = await event.get_chat()
    
    cleaned_text = re.sub(r'@\w+', '', message_text).strip()
    has_media = bool(event.message.media)
    
    if not cleaned_text and not has_media: 
        return
    
    final_text = f"{cleaned_text}{HASHTAGS}" if cleaned_text else HASHTAGS

    # Album handling (Debouncing via asyncio)
    if event.message.grouped_id:
        group_id = event.message.grouped_id
        
        if group_id not in ALBUM_CACHE:
            ALBUM_CACHE[group_id] = {
                'text': final_text if cleaned_text else HASHTAGS,
                'media_paths': [],
                'media_type': 'photo'
            }
            
            async def process_album(gid):
                await asyncio.sleep(5) 
                data = ALBUM_CACHE.pop(gid, None)
                if not data or not data['media_paths']: return
                
                logger.info(f"Album batch complete. Processing {len(data['media_paths'])} items.")
                post_to_facebook(data['text'], data['media_paths'], data['media_type'])
                
                for path in data['media_paths']:
                    if os.path.exists(path): os.remove(path)

            asyncio.create_task(process_album(group_id))
            
        media_path = await event.message.download_media(file="downloads/")
        if media_path:
            ALBUM_CACHE[group_id]['media_paths'].append(media_path)
            
        if cleaned_text:
            ALBUM_CACHE[group_id]['text'] = final_text
            
        return 

    # Single Post Handling
    logger.info(f"Processing single event from {chat.title}")
    try:
        if has_media:
            is_video = getattr(event.message, 'video', None) or (hasattr(event.message.media, 'document') and event.message.media.document.mime_type.startswith('video'))
            media_type = 'video' if is_video else 'photo'
            
            media_path = await event.message.download_media(file="downloads/")
            try:
                post_to_facebook(final_text, [media_path], media_type)
            finally:
                if media_path and os.path.exists(media_path): 
                    os.remove(media_path)
        else:
            post_to_facebook(final_text, None, None)

    except Exception as e:
        logger.error(f"Event processing error: {e}")

if __name__ == '__main__':
    if not os.path.exists("downloads"): 
        os.makedirs("downloads")
    
    logger.info("Initializing Telegram -> Facebook Bridge...")
    
    while True:
        try:
            client.start()
            logger.info(f"Listening to sources: {', '.join(str(c) for c in SOURCE_CHANNELS)}")
            client.run_until_disconnected()
        except Exception as e:
            logger.error(f"Network drop detected: {e}. Reconnecting in 5s...")
            time.sleep(5)
