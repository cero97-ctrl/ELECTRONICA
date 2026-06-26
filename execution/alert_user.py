#!/usr/bin/env python3
import sys
import json
import argparse

def main():
    parser = argparse.ArgumentParser(description="Emite notificaciones para el sistema.")
    parser.add_argument("status", choices=["success", "waiting", "error"], help="Estado a notificar.")
    parser.add_argument("--message", type=str, default="", help="Mensaje opcional de la notificación.")
    
    args = parser.parse_args()

    # Aquí se podría integrar con 'notify-send' o reproducir un sonido (.wav) con aplay.
    # Por ahora imprimimos a stdout.
    
    output = {
        "status": args.status,
        "message": args.message,
        "notified": True
    }
    
    print(json.dumps(output))
    
    if args.status == "error":
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    main()
