import yaml
import json
import socket
import logging
from typing import Dict, Any
from execution.ruview_signal_processing import procesar_paquete_ruview

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_directives(filepath: str) -> Dict[str, Any]:
    with open(filepath, 'r') as file:
        return yaml.safe_load(file)

def check_critical_vibration(acc_data: list, threshold: float) -> bool:
    """Verifica si el pico de vibración supera el umbral crítico."""
    if not acc_data:
        return False
    max_vib = max(abs(x) for x in acc_data)
    return max_vib > threshold

def flujo_principal():
    logging.info("Iniciando Orquestador RuView Rescue (Layer 2)...")
    
    # 1. Cargar Directivas (Layer 1)
    directives_path = "directives/ruview_rescue.yaml"
    try:
        directives = load_directives(directives_path)
        logging.info(f"Directivas cargadas: {directives['name']} v{directives['version']}")
    except FileNotFoundError:
        logging.error(f"No se encontró el archivo de directivas en {directives_path}")
        return

    # Extraer parámetros de las directivas
    steps = {step['action']: step for step in directives['steps']}
    
    port = steps['start_listener']['port']
    buffer_size = steps['start_listener']['buffer_size']
    vib_threshold = steps['check_vibration']['threshold']
    confidence_thresh = steps['emit_alert']['confidence_threshold']
    
    # 2. Configurar Servidor UDP
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", port))
    sock.settimeout(5.0) # 5 segundos de timeout
    logging.info(f"Escuchando paquetes UDP en el puerto {port}...")
    
    try:
        while True:
            try:
                data, addr = sock.recvfrom(buffer_size)
                # En producción esto vendría del ESP32-S3 empaquetado. 
                # Asumiremos un JSON para la simulación: {"csi": [0.1, 0.2...], "acc": [0.01, 0.05...]}
                payload = json.loads(data.decode('utf-8'))
                
                csi_data = payload.get("csi", [])
                acc_data = payload.get("acc", [])
                
                # 3. Revisión de seguridad (Vibración Crítica)
                if check_critical_vibration(acc_data, vib_threshold):
                    logging.warning("Vibración crítica detectada (Ej. Maquinaria pesada). Descartando ventana de lectura.")
                    continue
                
                # 4. Delegar a Capa de Ejecución (Layer 3)
                if csi_data and acc_data:
                    resultado = procesar_paquete_ruview(csi_data, acc_data, fs=100.0)
                    
                    if resultado["status"] == "success":
                        freq = resultado["dominant_frequency_hz"]
                        conf = resultado["confidence"]
                        bpm = resultado["bpm_estimado"]
                        
                        # 5. Evaluar resultados contra las directivas para alerta
                        if conf >= confidence_thresh:
                            logging.info(f"🚨 ¡ALERTA DE VIDA DETECTADA! 🚨")
                            logging.info(f"Frecuencia Respiratoria: {freq} Hz | BPM: {bpm} | Confianza: {conf:.2f}")
                        else:
                            logging.debug(f"Señal procesada. Freq: {freq} Hz (Confianza insuficiente: {conf:.2f})")
                    else:
                        logging.error(f"Error en Capa 3: {resultado.get('message')}")
                        
            except socket.timeout:
                # Solo para mantener el loop activo y poder interrumpir suavemente
                pass
            except json.JSONDecodeError:
                logging.error("Error al decodificar paquete JSON")
                
    except KeyboardInterrupt:
        logging.info("Interrupción del usuario. Cerrando orquestador.")
    finally:
        sock.close()
        logging.info("Servidor UDP cerrado.")

if __name__ == "__main__":
    flujo_principal()
