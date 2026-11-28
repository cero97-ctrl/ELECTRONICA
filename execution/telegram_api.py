import os
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables.")

BASE_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

# El offset se persiste para que un reinicio del servicio (o del motor) NO
# reprocese mensajes antiguos. Sin esto, un `/confirmar` del historial podría
# volver a ejecutarse al arrancar. Es un archivo derivado y regenerable: vive en
# .tmp/, nunca viaja a git.
OFFSET_PATH = Path(os.getenv("TELEGRAM_OFFSET_FILE", ".tmp/telegram_offset.txt"))


def leer_offset() -> int | None:
    """Devuelve el último update_id confirmado, o None si aún no hay uno."""
    try:
        valor = OFFSET_PATH.read_text(encoding="utf-8").strip()
    except (OSError, ValueError):
        return None
    return int(valor) if valor.isdigit() else None


def guardar_offset(offset: int) -> None:
    """Persiste el offset de forma atómica (escritura + rename)."""
    OFFSET_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporal = OFFSET_PATH.with_suffix(".tmp")
    temporal.write_text(str(int(offset)), encoding="utf-8")
    os.replace(temporal, OFFSET_PATH)

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
