#!/usr/bin/env python3
import urllib.request
import urllib.error
import json
import os
import sys

def test_worker(base_url="http://localhost:8787"):
    print(f"Iniciando pruebas sobre el Cloudflare Worker local en: {base_url}\n")
    
    # 1. Probar Endpoint de Estado (GET /status)
    try:
        print("[Prueba 1] GET /status")
        req = urllib.request.Request(
            f"{base_url}/status", 
            headers={"User-Agent": "Mozilla/5.0"},
            method="GET"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            status_code = response.getcode()
            body = response.read().decode('utf-8')
            print(f"  Status Code: {status_code}")
            data = json.loads(body)
            print(f"  Respuesta JSON: {json.dumps(data, indent=2)}")
            assert data.get("status") == "ok"
            print("  ✓ Prueba 1 exitosa.\n")
    except Exception as e:
        print(f"  x Fallo en Prueba 1: {e}")
        return False

    # 2. Probar Endpoint de Chat (POST /chat)
    try:
        print("[Prueba 2] POST /chat (Groq - Llama)")
        payload = {
            "message": "Explica brevemente qué es un diodo Zener en una sola frase.",
            "provider": "groq"
        }
        req_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            f"{base_url}/chat",
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            },
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            status_code = response.getcode()
            body = response.read().decode('utf-8')
            print(f"  Status Code: {status_code}")
            data = json.loads(body)
            print(f"  Respuesta del Agente: {data.get('response')}")
            assert "response" in data
            print("  ✓ Prueba 2 exitosa.\n")
    except Exception as e:
        print(f"  x Fallo en Prueba 2: {e}")
        return False

    # 3. Probar Endpoint de Cotización (POST /quote)
    try:
        print("[Prueba 3] POST /quote (Generación de PDF)")
        payload = {
            "clientName": "Prof. César Rodríguez",
            "clientEmail": "carlos@example.com",
            "items": [
                {"description": "Asesoría en Diseño PCB", "quantity": 1, "price": 300.00},
                {"description": "Microcontrolador ESP32-WROOM-32D", "quantity": 5, "price": 4.50}
            ],
            "notes": "Validez de la oferta: 30 días. Sujeto a stock."
        }
        req_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            f"{base_url}/quote",
            data=req_data,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0"
            },
            method="POST"
        )
        
        # Asegurar que el directorio .tmp existe
        os.makedirs(".tmp", exist_ok=True)
        pdf_path = ".tmp/cotizacion_test.pdf"
        
        with urllib.request.urlopen(req, timeout=15) as response:
            status_code = response.getcode()
            content_type = response.headers.get("Content-Type")
            print(f"  Status Code: {status_code}")
            print(f"  Content-Type: {content_type}")
            
            assert "application/pdf" in content_type
            
            pdf_bytes = response.read()
            with open(pdf_path, "wb") as f:
                f.write(pdf_bytes)
            
            file_size = os.path.getsize(pdf_path)
            print(f"  PDF guardado en: {pdf_path} ({file_size} bytes)")
            assert file_size > 0
            print("  ✓ Prueba 3 exitosa.\n")
    except Exception as e:
        print(f"  x Fallo en Prueba 3: {e}")
        return False

    print("=== TODAS LAS PRUEBAS COMPLETADAS CON ÉXITO ===")
    return True

if __name__ == "__main__":
    url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8787"
    success = test_worker(url)
    sys.exit(0 if success else 1)
