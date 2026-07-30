#include <Arduino.h>
#include <TFT_eSPI.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <esp_camera.h>
#include "CameraServer.h"

// --- CONFIGURACIÓN DEL WiFi (Punto de Acceso) ---
const char* ssid     = "ESP32-S3-LAB";
const char* password = "labpassword";

// --- OBJETOS ---
TFT_eSPI tft = TFT_eSPI();
AsyncWebServer server(80);

// --- PIN BACKLIGHT (Actualizado a 40) ---
#define PIN_BLK 40

// --- PINES CÁMARA (Freenove WROOM S3) ---
#define PWDN_GPIO_NUM    -1
#define RESET_GPIO_NUM   -1
#define XCLK_GPIO_NUM    15
#define SIOD_GPIO_NUM    4
#define SIOC_GPIO_NUM    5
#define Y9_GPIO_NUM      16
#define Y8_GPIO_NUM      17
#define Y7_GPIO_NUM      18
#define Y6_GPIO_NUM      12
#define Y5_GPIO_NUM      10
#define Y4_GPIO_NUM      8
#define Y3_GPIO_NUM      9
#define Y2_GPIO_NUM      11
#define VSYNC_GPIO_NUM   6
#define HREF_GPIO_NUM    7
#define PCLK_GPIO_NUM    13

// --- ESP-NOW ---
uint8_t broadcastAddress[] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};
esp_now_peer_info_t peerInfo;

typedef struct struct_message {
  uint8_t cmdType;
  bool state;
  char text[32];
} struct_message;

struct_message myData;
bool cameraActive = false;

typedef struct sensor_message {
  float temperature;
  float distance;
  int light;
  int potentiometer;
  bool tilt;
} sensor_message;

sensor_message incomingSensors = {0, 0, 0, 0, false};

void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("\r\nUltimo paquete enviado: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Exito" : "Fallo");
}

void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  if (len == sizeof(sensor_message)) {
    memcpy(&incomingSensors, incomingData, sizeof(incomingSensors));
  }
}

void sendCommand(uint8_t cmdType, bool state, const char* text = "") {
  myData.cmdType = cmdType;
  myData.state = state;
  if(text != nullptr) {
    strncpy(myData.text, text, sizeof(myData.text));
    myData.text[sizeof(myData.text)-1] = '\0';
  } else {
    myData.text[0] = '\0';
  }
  esp_now_send(broadcastAddress, (uint8_t *) &myData, sizeof(myData));
}

bool initCamera() {
  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = Y2_GPIO_NUM;
  config.pin_d1 = Y3_GPIO_NUM;
  config.pin_d2 = Y4_GPIO_NUM;
  config.pin_d3 = Y5_GPIO_NUM;
  config.pin_d4 = Y6_GPIO_NUM;
  config.pin_d5 = Y7_GPIO_NUM;
  config.pin_d6 = Y8_GPIO_NUM;
  config.pin_d7 = Y9_GPIO_NUM;
  config.pin_xclk = XCLK_GPIO_NUM;
  config.pin_pclk = PCLK_GPIO_NUM;
  config.pin_vsync = VSYNC_GPIO_NUM;
  config.pin_href = HREF_GPIO_NUM;
  config.pin_sccb_sda = SIOD_GPIO_NUM;
  config.pin_sccb_scl = SIOC_GPIO_NUM;
  config.pin_pwdn = PWDN_GPIO_NUM;
  config.pin_reset = RESET_GPIO_NUM;
  config.xclk_freq_hz = 10000000;
  config.frame_size = FRAMESIZE_QVGA;
  config.pixel_format = PIXFORMAT_JPEG;
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 20;
  config.fb_count = 1;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed: 0x%x\n", err);
    return false;
  }
  Serial.println("Camara iniciada OK");
  return true;
}

void deinitCamera() {
  esp_camera_deinit();
  Serial.println("Camara detenida");
}

// --- PÁGINA WEB HTML ---
const char paginaHTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ESP32-S3 LAB Dashboard</title>
  <style>
    body { font-family: 'Segoe UI', Arial, sans-serif; background: #1a1a2e; color: white; display: flex; flex-direction: column; align-items: center; padding: 20px; }
    h1 { color: #e94560; }
    .card { background: #16213e; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.5); margin: 10px; width: 320px; text-align: center; }
    button { background: #0f3460; color: white; border: none; padding: 10px; border-radius: 5px; cursor: pointer; font-size: 14px; margin: 5px; transition: 0.3s; width: 80px; }
    button:hover { background: #e94560; }
    .btn-on { background: #4caf50; }
    .btn-off { background: #f44336; }
    .btn-full { width: 90%; background: #667eea; }
    input[type=text] { padding: 10px; width: 85%; border-radius: 5px; border: none; margin-bottom: 10px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .led-control { display: flex; flex-direction: column; align-items: center; background: rgba(255,255,255,0.05); padding: 10px; border-radius: 8px; }
    .camera-container { width: 100%; border-radius: 8px; overflow: hidden; background: black; min-height: 60px; display: flex; align-items: center; justify-content: center; }
    .camera-container img { width: 100%; display: block; }
    .btn-cam { width: 90%; padding: 12px; font-size: 16px; font-weight: bold; border-radius: 8px; }
    .cam-off { background: #4caf50; }
    .cam-on { background: #f44336; }
  </style>
</head>
<body>
  <h1>ESP32 LAB Control</h1>

  <div class="card" style="width: 90%; max-width: 800px;">
    <h2>Sensores Kids Lab</h2>
    <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 15px;">
      <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px;">
        <h3 style="margin: 0; color: #667eea; font-size: 16px;">Temperatura</h3>
        <p style="font-size: 24px; font-weight: bold; margin: 10px 0;"><span id="tempValue">--.-</span> °C</p>
      </div>
      <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px;">
        <h3 style="margin: 0; color: #667eea; font-size: 16px;">Distancia</h3>
        <p style="font-size: 24px; font-weight: bold; margin: 10px 0;"><span id="distValue">--</span> cm</p>
      </div>
      <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px;">
        <h3 style="margin: 0; color: #667eea; font-size: 16px;">Luz (LDR)</h3>
        <p style="font-size: 24px; font-weight: bold; margin: 10px 0;"><span id="lightValue">--</span></p>
      </div>
      <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px;">
        <h3 style="margin: 0; color: #667eea; font-size: 16px;">Potenciómetro</h3>
        <p style="font-size: 24px; font-weight: bold; margin: 10px 0;"><span id="potValue">--</span></p>
      </div>
      <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px;">
        <h3 style="margin: 0; color: #667eea; font-size: 16px;">Inclinación</h3>
        <p style="font-size: 24px; font-weight: bold; margin: 10px 0;"><span id="tiltValue">--</span></p>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Cámara en Vivo</h2>
    <div class="camera-container" id="cam-box">
      <img id="cam-stream" src="" alt="" style="display:none;">
      <p id="cam-off-msg" style="color: #888;">Cámara apagada</p>
    </div>
    <button id="camBtn" class="btn-cam cam-off" onclick="toggleCamera()" style="margin-top:10px;">ENCENDER CÁMARA</button>
  </div>
  
  <div class="card">
    <h2>LEDs y Actuadores</h2>
    <div class="grid">
      <div class="led-control">
        <p>Rojo</p>
        <div>
          <button class="btn-on" onclick="sendCmd(1, true)">ON</button>
          <button class="btn-off" onclick="sendCmd(1, false)">OFF</button>
        </div>
      </div>
      <div class="led-control">
        <p>Verde</p>
        <div>
          <button class="btn-on" onclick="sendCmd(2, true)">ON</button>
          <button class="btn-off" onclick="sendCmd(2, false)">OFF</button>
        </div>
      </div>
      <div class="led-control">
        <p>Azul</p>
        <div>
          <button class="btn-on" onclick="sendCmd(3, true)">ON</button>
          <button class="btn-off" onclick="sendCmd(3, false)">OFF</button>
        </div>
      </div>
      <div class="led-control">
        <p>Amarillo</p>
        <div>
          <button class="btn-on" onclick="sendCmd(4, true)">ON</button>
          <button class="btn-off" onclick="sendCmd(4, false)">OFF</button>
        </div>
      </div>
    </div>
    
    <div style="margin-top: 20px;" class="grid">
      <div class="led-control">
          <p>Rele Principal</p>
          <div>
            <button class="btn-on" style="width: 100px;" onclick="sendCmd(5, true)">ON</button>
            <button class="btn-off" style="width: 100px;" onclick="sendCmd(5, false)">OFF</button>
          </div>
      </div>
      <div class="led-control">
          <p>Buzzer</p>
          <div style="display: flex; gap: 5px; flex-direction: column; align-items: center;">
            <div style="display: flex; gap: 5px;">
              <button class="btn-on" style="width: 50px;" onclick="sendCmd(7, true)">ON</button>
              <button class="btn-off" style="width: 50px;" onclick="sendCmd(7, false)">OFF</button>
            </div>
            <div style="display: flex; gap: 5px; align-items: center;">
              <input type="number" id="buzzTime" value="500" style="width: 50px; padding: 5px; margin: 0; text-align: center;">
              <button class="btn-on" style="width: 50px; background: #667eea; padding: 6px;" onclick="sendBuzz()">ms</button>
            </div>
          </div>
      </div>
      <div class="led-control">
          <p>Matriz LED</p>
          <div>
            <button class="btn-on" style="width: 100px;" onclick="sendCmd(8, true)">ON</button>
            <button class="btn-off" style="width: 100px;" onclick="sendCmd(8, false)">OFF</button>
          </div>
      </div>
      <div class="led-control">
          <p>Display 7 Seg</p>
          <div style="display: flex; gap: 5px; flex-direction: column; align-items: center;">
            <div style="display: flex; gap: 5px;">
              <input type="number" id="segText" placeholder="1234" style="width: 60px; padding: 5px; margin: 0; text-align: center;">
              <button class="btn-on" style="width: 60px; background: #667eea; padding: 6px;" onclick="send7Seg()">Enviar</button>
            </div>
            <button class="btn-off" style="width: 120px;" onclick="sendCmd(9, false)">APAGAR</button>
          </div>
      </div>
    </div>
  </div>

  <div class="card">
    <h2>Pantalla OLED</h2>
    <input type="text" id="oledText" placeholder="Escribe un mensaje...">
    <br>
    <button class="btn-full" onclick="sendOled()">Enviar a Pantalla</button>
  </div>

  <script>
    const cam = document.getElementById('cam-stream');
    const camBtn = document.getElementById('camBtn');
    const camOffMsg = document.getElementById('cam-off-msg');
    let isFetching = false;
    let camStreaming = false;
    
    function updateFrame() {
      if(!camStreaming || isFetching) return;
      isFetching = true;
      cam.src = "http://192.168.4.1:81/capture?_cb=" + Date.now();
    }
    
    cam.onload = () => { isFetching = false; if(camStreaming) setTimeout(updateFrame, 300); };
    cam.onerror = () => { isFetching = false; if(camStreaming) setTimeout(updateFrame, 2000); };
    
    function toggleCamera() {
      camBtn.disabled = true;
      camBtn.textContent = 'Procesando...';
      fetch('/api/camera', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ action: camStreaming ? 'off' : 'on' })
      })
      .then(r => r.json())
      .then(d => {
        if(d.camera) {
          camStreaming = true;
          cam.style.display = 'block';
          camOffMsg.style.display = 'none';
          camBtn.textContent = 'APAGAR CÁMARA';
          camBtn.className = 'btn-cam cam-on';
          updateFrame();
        } else {
          camStreaming = false;
          cam.style.display = 'none';
          cam.src = '';
          camOffMsg.style.display = 'block';
          camBtn.textContent = 'ENCENDER CÁMARA';
          camBtn.className = 'btn-cam cam-off';
        }
        camBtn.disabled = false;
      })
      .catch(() => { camBtn.disabled = false; camBtn.textContent = 'Error, reintentar'; });
    }

    function sendBuzz() {
      let duration = document.getElementById('buzzTime').value;
      fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmdType: 7, state: true, text: duration })
      });
    }

    function sendCmd(type, state) {
      fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmdType: type, state: state })
      });
    }
    function sendOled() {
      let text = document.getElementById('oledText').value;
      fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmdType: 6, text: text })
      });
    }
    
    function send7Seg() {
      let num = document.getElementById('segText').value;
      fetch('/api/control', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmdType: 9, state: true, text: num })
      });
    }

    // Polling de Sensores
    setInterval(() => {
      fetch('/api/sensors')
        .then(r => r.json())
        .then(data => {
          document.getElementById('tempValue').innerText = data.temperature > -100 ? data.temperature.toFixed(1) : "Error";
          document.getElementById('distValue').innerText = data.distance > 0 ? data.distance.toFixed(0) : "---";
          document.getElementById('lightValue').innerText = data.light;
          document.getElementById('potValue').innerText = data.potentiometer;
          document.getElementById('tiltValue').innerText = data.tilt ? "Inclinado" : "Plano";
          document.getElementById('tiltValue').style.color = data.tilt ? "#e94560" : "white";
        })
        .catch(e => console.log("Error leyendo sensores"));
    }, 2000);
  </script>
</body>
</html>
)rawliteral";

void setup() {
  Serial.begin(115200);
  
  // Inicializar Backlight TFT
  pinMode(PIN_BLK, OUTPUT);
  digitalWrite(PIN_BLK, HIGH);
  
  // Inicializar pantalla TFT
  tft.init();
  tft.setRotation(0);
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.setCursor(5, 10);
  tft.println("ESP32-S3 LAB");
  tft.println("Iniciando AP y Camara...");

  // Inicializar Wi-Fi
  WiFi.disconnect(true);
  WiFi.softAPdisconnect(true);
  delay(100);
  WiFi.mode(WIFI_AP);
  delay(100);
  WiFi.setTxPower(WIFI_POWER_17dBm);  // Potencia alta pero estable
  IPAddress local_ip(192, 168, 4, 1);
  IPAddress gateway(192, 168, 4, 1);
  IPAddress subnet(255, 255, 255, 0);
  WiFi.softAPConfig(local_ip, gateway, subnet);
  WiFi.softAP(ssid, password, 1, 0, 4);  // Canal 1, no oculto, max 4 clientes
  
  delay(1000);  // Esperar a que el AP se estabilice completamente
  
  // Desactivar ahorro de energía WiFi — evita que el AP desconecte clientes
  esp_wifi_set_ps(WIFI_PS_NONE);
  
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());
  
  // Servidor de cámara (puerto 81) — siempre activo, pero la cámara arranca APAGADA
  startCameraServer();
  Serial.println("Camera server en puerto 81 (camara apagada)");

  // Mostrar info en TFT
  tft.fillScreen(TFT_BLACK);
  tft.setCursor(5, 10);
  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.println("WiFi & Cam Listo!");
  
  tft.setTextSize(1);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.println("\nSSID:");
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.println(ssid);
  
  tft.setTextSize(1);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.println("\nPassword:");
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.println(password);
  
  tft.setTextSize(1);
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.println("\nIP Dashboard Web:");
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.setTextSize(2);
  tft.println(WiFi.softAPIP());

  // Inicializar ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error ESP-NOW");
    return;
  }
  esp_now_register_send_cb(OnDataSent);
  esp_now_register_recv_cb(OnDataRecv);
  
  memset(&peerInfo, 0, sizeof(peerInfo));
  memcpy(peerInfo.peer_addr, broadcastAddress, 6);
  peerInfo.channel = 1;  
  peerInfo.ifidx = WIFI_IF_AP;  
  peerInfo.encrypt = false;
  
  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Error agregando peer ESP-NOW");
    return;
  }

  // Web Server Dashboard
  server.on("/", HTTP_GET, [](AsyncWebServerRequest *request){
    request->send(200, "text/html", paginaHTML);
  });

  server.on("/api/control", HTTP_POST, [](AsyncWebServerRequest *request){
    request->send(200, "application/json", "{\"status\":\"ok\"}");
  }, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total){
    StaticJsonDocument<200> doc;
    if (!deserializeJson(doc, (const char*)data, len)) {
      uint8_t cmd = doc["cmdType"];
      if((cmd >= 1 && cmd <= 5) || cmd == 7 || cmd == 8 || cmd == 9) {
        bool state = doc["state"];
        const char* text = doc.containsKey("text") ? doc["text"].as<const char*>() : "";
        sendCommand(cmd, state, text);
      } else if (cmd == 6) {
        const char* text = doc["text"];
        sendCommand(cmd, false, text);
      }
    }
  });

  server.on("/api/camera", HTTP_POST, [](AsyncWebServerRequest *request){
    request->send(200, "application/json", "{\"status\":\"ok\"}");
  }, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total){
    StaticJsonDocument<100> doc;
    if (!deserializeJson(doc, (const char*)data, len)) {
      const char* action = doc["action"];
      if (strcmp(action, "on") == 0 && !cameraActive) {
        if (initCamera()) {
          cameraActive = true;
        }
      } else if (strcmp(action, "off") == 0 && cameraActive) {
        deinitCamera();
        cameraActive = false;
      }
      String resp = "{\"camera\":" + String(cameraActive ? "true" : "false") + "}";
      request->send(200, "application/json", resp);
    }
  });

  server.on("/api/sensors", HTTP_GET, [](AsyncWebServerRequest *request){
    String json = "{";
    json += "\"temperature\": " + String(incomingSensors.temperature, 1) + ",";
    json += "\"distance\": " + String(incomingSensors.distance, 1) + ",";
    json += "\"light\": " + String(incomingSensors.light) + ",";
    json += "\"potentiometer\": " + String(incomingSensors.potentiometer) + ",";
    json += "\"tilt\": " + String(incomingSensors.tilt ? "true" : "false");
    json += "}";
    request->send(200, "application/json", json);
  });

  server.begin();
}

void loop() {
  delay(100);
}
