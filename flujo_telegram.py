import os
import sys
import yaml
import time
from dotenv import load_dotenv

from execution.telegram_api import get_updates, send_message
from execution.mcp_client import call_mcp_tool

def load_config():
    directive_path = os.path.join("directives", "telegram_gateway.yaml")
    with open(directive_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)

def process_message(message, config):
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    username = message["chat"].get("username", "Unknown")
    
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Message from {username} (ID: {chat_id}): {text}")
    
    # 1. Security Check
    allowed_ids = config["configuration"]["security"]["allowed_chat_ids"]
    if not allowed_ids:
        send_message(chat_id, f"⚠️ Tu Chat ID es: `{chat_id}`. Aún no hay usuarios autorizados. Por favor, añade este ID a la lista `allowed_chat_ids` en `directives/telegram_gateway.yaml`.")
        return
        
    if chat_id not in allowed_ids:
        print(f"Acceso denegado para el chat_id {chat_id}")
        # Logged, but no response as per directive "Log rejected attempts but do not reply to them"
        return
        
    # 2. Command Parsing (Simple mapping)
    text = text.strip()
    if text == "/start" or text == "/help":
        help_text = (
            "🤖 *Telegram Gateway MCP*\n\n"
            "Comandos disponibles:\n"
            "`/ping` - Prueba de conectividad\n"
            "`/diagnostico` - Ejecuta el servidor de diagnóstico\n"
            "`/latex <código>` - Compila código LaTeX\n"
            "*(Otros comandos en desarrollo)*"
        )
        send_message(chat_id, help_text)
        return
        
    if text == "/ping":
        send_message(chat_id, "🏓 Pong! El Gateway está activo y escuchando.")
        return
        
    # 3. Routing to MCP Servers
    mcp_servers = config["configuration"]["mcp_servers"]
    
    if text.startswith("/diagnostico"):
        send_message(chat_id, "Iniciando diagnóstico local...")
        server_script = mcp_servers.get("diagnostico")
        if server_script:
            result = call_mcp_tool(server_script, "generar_diagnostico_sistema", {})
            if len(result) > 4000:
                result = result[:4000] + "\n...[truncado]"
            # El resultado ya puede traer markdown, así que lo enviamos tal cual, 
            # pero sin parse_mode si queremos evitar errores, o lo dejamos así
            # ya que el servidor diagnostico envía json que puede chocar con markdown normal.
            # Vamos a quitar el envoltorio extra y usar parse_mode=None para evitar fallos.
            send_message(chat_id, f"📝 Resultado del Diagnóstico:\n\n{result}", parse_mode=None)
        return
        
    if text.startswith("/latex"):
        codigo = text.replace("/latex", "", 1).strip()
        if not codigo:
            send_message(chat_id, "⚠️ Debes proveer código LaTeX. Ejemplo: `/latex \\documentclass...`")
            return
            
        send_message(chat_id, "Compilando LaTeX localmente...")
        server_script = mcp_servers.get("latex")
        if server_script:
            result = call_mcp_tool(server_script, "compilar_latex", {"codigo_latex": codigo})
            if len(result) > 4000:
                result = result[:4000] + "\n...[truncado]"
            send_message(chat_id, f"📝 Resultado de Compilación:\n\n{result}", parse_mode=None)
        return

        
    send_message(chat_id, "❌ Comando no reconocido. Usa /help para ver las opciones.")

def main():
    print("Iniciando Telegram Gateway Orquestador...")
    config = load_config()
    timeout = config["configuration"]["telegram"]["poll_timeout"]
    
    offset = None
    
    print(f"Escuchando mensajes (Long Polling timeout: {timeout}s)...")
    try:
        while True:
            updates = get_updates(offset=offset, timeout=timeout)
            if updates and "result" in updates:
                for update in updates["result"]:
                    # Update offset to acknowledge receipt
                    offset = update["update_id"] + 1
                    
                    if "message" in update:
                        process_message(update["message"], config)
                        
            time.sleep(1) # Pequeña pausa para no saturar la CPU en caso de errores continuos
    except KeyboardInterrupt:
        print("\nApagando Telegram Gateway...")

if __name__ == "__main__":
    main()
