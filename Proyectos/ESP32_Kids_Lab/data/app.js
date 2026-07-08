// Estado Global
let sensors = { distance: 0, light: 0, temperature: 0 };
let actuators = { red: false, green: false, blue: false, yellow: false, relay: false, buzzer: false };
let activeExperiment = null;

// Elementos UI
const connStatus = document.getElementById('conn-status');
const connText = document.getElementById('conn-text');

// Polling de Sensores cada 1 segundo
setInterval(async () => {
    try {
        const res = await fetch('/api/sensors');
        if (!res.ok) throw new Error('Network response was not ok');
        const data = await res.json();
        
        sensors = data;
        updateSensorsUI();
        evaluateExperiments();

        // Actualizar UI de conexión
        connStatus.className = 'dot connected';
        connText.innerText = 'Conectado';
    } catch (err) {
        console.error('Error fetching sensors:', err);
        connStatus.className = 'dot disconnected';
        connText.innerText = 'Desconectado';
    }
}, 1000);

// Actualiza los valores y barras de progreso
function updateSensorsUI() {
    // Distancia (Asumimos max 100cm para la barra)
    const dist = Math.min(Math.max(sensors.distance, 0), 100);
    document.getElementById('val-distance').innerText = `${Math.round(sensors.distance)} cm`;
    document.getElementById('bar-distance').style.width = `${dist}%`;

    // Luz (Asumimos max 4095 para la barra)
    const lightPct = (sensors.light / 4095) * 100;
    document.getElementById('val-light').innerText = sensors.light;
    document.getElementById('bar-light').style.width = `${lightPct}%`;

    // Temperatura (Asumimos max 50°C para la barra)
    const tempPct = (sensors.temperature / 50) * 100;
    document.getElementById('val-temp').innerText = `${sensors.temperature.toFixed(1)} °C`;
    document.getElementById('bar-temp').style.width = `${Math.min(tempPct, 100)}%`;
}

// Enviar comandos al ESP32
async function sendCommand(payload) {
    // Actualizamos estado local
    actuators = { ...actuators, ...payload };

    try {
        await fetch('/api/actuators', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
    } catch (err) {
        console.error('Error sending command:', err);
    }
}

// Funciones de botones/switches directos
function toggleDevice(device, state) {
    if (activeExperiment) return; // Bloquear control manual si hay un experimento activo
    const payload = {};
    payload[device] = state;
    sendCommand(payload);
}

// Control especial para el botón del relé
function toggleRelay() {
    if (activeExperiment) return;
    const newState = !actuators.relay;
    sendCommand({ relay: newState });
    const btn = document.getElementById('btn-relay');
    btn.innerText = newState ? '¡Desactivar!' : '¡Activar!';
    btn.style.filter = newState ? 'hue-rotate(180deg)' : 'none';
}

// Lógica de Experimentos (Mini-juegos en JavaScript)
function toggleExperiment(expName) {
    const isChecked = document.getElementById(`exp-${expName}`).checked;
    
    // Apagar otros experimentos
    if (isChecked) {
        if (expName !== 'radar') document.getElementById('exp-radar').checked = false;
        if (expName !== 'lamp') document.getElementById('exp-lamp').checked = false;
        activeExperiment = expName;
    } else {
        activeExperiment = null;
        // Apagar actuadores al salir
        sendCommand({ red: false, yellow: false, relay: false, buzzer: false });
    }
}

function evaluateExperiments() {
    if (!activeExperiment) return;

    if (activeExperiment === 'radar') {
        // Regla: Si distancia < 15cm -> Alarma
        if (sensors.distance > 0 && sensors.distance < 15) {
            sendCommand({ red: true, buzzer: true });
        } else {
            sendCommand({ red: false, buzzer: false });
        }
    }

    if (activeExperiment === 'lamp') {
        // Regla: Si hay poca luz (valor analógico alto en fotorresistencia en pull-down o al revés)
        // Ajustar umbral según sensor real. Asumimos < 1000 es poca luz.
        if (sensors.light < 1000) {
            sendCommand({ yellow: true });
        } else {
            sendCommand({ yellow: false });
        }
    }
}

// Control del Display
async function sendDisplay() {
    const val = parseInt(document.getElementById('display-input').value);
    if(isNaN(val)) return;
    try {
        await fetch('/api/display', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ number: val })
        });
    } catch(err) { console.error(err); }
}

async function clearDisplay() {
    try {
        await fetch('/api/display', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ clear: true })
        });
        document.getElementById('display-input').value = "";
    } catch(err) { console.error(err); }
}

// Control de la Matriz NeoPixel
async function sendMatrix(r, g, b) {
    try {
        await fetch('/api/matrix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ r: r, g: g, b: b })
        });
    } catch(err) { console.error(err); }
}

async function clearMatrix() {
    try {
        await fetch('/api/matrix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ clear: true })
        });
    } catch(err) { console.error(err); }
}

// === Lógica del Estudio Pixel Art ===
let currentPixelColor = [255, 0, 0];
let pixelColorsArray = Array.from({length: 16}, () => [0, 0, 0]);
let debounceTimer = null;

function initPixelGrid() {
    const grid = document.getElementById('pixel-grid');
    if (!grid) return;
    grid.innerHTML = '';
    for (let i = 0; i < 16; i++) {
        let cell = document.createElement('div');
        cell.className = 'pixel-cell';
        cell.onclick = () => paintPixel(i, cell);
        grid.appendChild(cell);
    }
}

function selectColor(colorArr, btnElement) {
    currentPixelColor = colorArr;
    document.querySelectorAll('.color-btn').forEach(btn => btn.classList.remove('active'));
    btnElement.classList.add('active');
}

function paintPixel(index, cell) {
    pixelColorsArray[index] = [...currentPixelColor];
    cell.style.backgroundColor = `rgb(${currentPixelColor[0]}, ${currentPixelColor[1]}, ${currentPixelColor[2]})`;
    
    // Enviar en vivo con debounce de 100ms para no saturar
    if (debounceTimer) clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => {
        sendPixelArray();
    }, 100);
}

async function sendPixelArray() {
    try {
        await fetch('/api/matrix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pixels: pixelColorsArray })
        });
    } catch(err) { console.error(err); }
}

function clearPixelArt() {
    pixelColorsArray = Array.from({length: 16}, () => [0, 0, 0]);
    document.querySelectorAll('.pixel-cell').forEach(cell => {
        cell.style.backgroundColor = '#000';
    });
    clearMatrix(); // Ya existe, limpia la física
}

// Inicializar la grilla cuando cargue la página
document.addEventListener('DOMContentLoaded', initPixelGrid);

