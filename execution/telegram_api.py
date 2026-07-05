import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables.")

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

def get_updates(offset=None, timeout=30):
    """
    Fetches new messages from Telegram using Long Polling.
    """
    url = f"{BASE_URL}/getUpdates"
    params = {
        "timeout": timeout,
        "allowed_updates": ["message"]
    }
    if offset:
        params["offset"] = offset
        
    try:
        # Request timeout needs to be slightly larger than long polling timeout
        response = requests.get(url, params=params, timeout=timeout + 5)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[Telegram API] Error getting updates: {e}")
        return None

def send_message(chat_id, text, parse_mode="Markdown"):
    """
    Sends a message to a specific chat_id.
    """
    url = f"{BASE_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
    }
    
    if parse_mode:
        payload["parse_mode"] = parse_mode
        
    try:
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"[Telegram API] Error sending message: {e}")
        return None
