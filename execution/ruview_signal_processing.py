import numpy as np
from scipy.signal import butter, lfilter
from typing import Dict, Any, Tuple

def butter_bandpass(lowcut: float, highcut: float, fs: float, order: int = 5) -> Tuple[np.ndarray, np.ndarray]:
    """Diseña un filtro pasabanda de Butterworth."""
    nyq = 0.5 * fs
    low = lowcut / nyq
    high = highcut / nyq
    b, a = butter(order, [low, high], btype='band')
    return b, a

def apply_bandpass_filter(data: np.ndarray, lowcut: float, highcut: float, fs: float, order: int = 5) -> np.ndarray:
    """Aplica un filtro pasabanda."""
    b, a = butter_bandpass(lowcut, highcut, fs, order=order)
    y = lfilter(b, a, data)
    return y

def apply_nlms_filter(csi_signal: np.ndarray, acc_reference: np.ndarray, mu: float = 0.1, filter_order: int = 32) -> np.ndarray:
    """
    Aplica un filtro adaptativo NLMS (Normalized Least Mean Squares).
    Resta la referencia de vibración mecánica (acc_reference) de la señal (csi_signal).
    """
    n = len(csi_signal)
    w = np.zeros(filter_order)
    output = np.zeros(n)
    error = np.zeros(n)
    
    # Aseguramos que ambas señales tengan el mismo tamaño
    min_len = min(len(csi_signal), len(acc_reference))
    
    for i in range(filter_order, min_len):
        x = acc_reference[i-filter_order:i]
        
        # Predicción del ruido basado en el acelerómetro
        y_hat = np.dot(w, x)
        
        # El error es la señal limpia (CSI original - Predicción del ruido mecánico)
        e = csi_signal[i] - y_hat
        
        # Normalización para NLMS
        norm = np.dot(x, x) + 1e-6
        
        # Actualización de pesos
        w = w + (mu / norm) * e * x
        
        output[i] = e
        
    return output

def procesar_paquete_ruview(csi_data: list, acc_data: list, fs: float = 100.0) -> Dict[str, Any]:
    """
    Función de ejecución (Layer 3).
    Recibe la ventana de datos CSI y los datos de referencia del acelerómetro.
    Aplica NLMS y luego busca frecuencias de respiración.
    """
    try:
        csi_array = np.array(csi_data)
        acc_array = np.array(acc_data)
        
        # 1. Filtro Adaptativo: Eliminar el ruido de maquinaria de la señal CSI
        # Asumimos que acc_data es la magnitud del vector de aceleración o el eje principal.
        clean_csi = apply_nlms_filter(csi_array, acc_array)
        
        # 2. Filtrado pasabanda para buscar frecuencias de respiración (0.2 a 0.5 Hz)
        filtered_resp = apply_bandpass_filter(clean_csi, lowcut=0.2, highcut=0.5, fs=fs)
        
        # 3. Análisis en frecuencia (FFT rápida) para determinar si hay respiración
        N = len(filtered_resp)
        fft_out = np.abs(np.fft.rfft(filtered_resp))
        freqs = np.fft.rfftfreq(N, 1.0/fs)
        
        # Buscar el pico máximo de la FFT
        max_idx = np.argmax(fft_out)
        dominant_freq = freqs[max_idx]
        confidence = fft_out[max_idx] / (np.sum(fft_out) + 1e-6)
        
        return {
            "status": "success",
            "clean_csi_sample": clean_csi.tolist()[-5:], # Solo retornamos los ultimos por brevedad
            "dominant_frequency_hz": round(dominant_freq, 3),
            "confidence": round(confidence, 3),
            "bpm_estimado": round(dominant_freq * 60, 1)
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }
