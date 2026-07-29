#include <Arduino.h>
#include <TFT_eSPI.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <ArduinoJson.h>
#include <esp_now.h>
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

void OnDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("\r\nUltimo paquete enviado: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Exito" : "Fallo");
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
    .camera-container { width: 100%; border-radius: 8px; overflow: hidden; background: black; }
    .camera-container img { width: 100%; display: block; }
  </style>
</head>
<body>
  <h1>ESP32 LAB Control</h1>

  <div class="card">
    <h2>Cámara en Vivo</h2>
    <div class="camera-container">
      <img id="cam-stream" src="" alt="Stream de Cámara">
    </div>
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
    
    <div style="margin-top: 20px;" class="led-control">
        <p>Rele Principal</p>
        <div>
          <button class="btn-on" style="width: 120px;" onclick="sendCmd(5, true)">ACTIVAR</button>
          <button class="btn-off" style="width: 120px;" onclick="sendCmd(5, false)">DESACTIVAR</button>
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
    let isFetching = false;
    
    function updateFrame() {
      if(isFetching) return;
      isFetching = true;
      cam.src = "http://192.168.4.1:81/capture?_cb=" + Date.now();
    }
    
    cam.onload = () => { isFetching = false; setTimeout(updateFrame, 50); };
    cam.onerror = () => { isFetching = false; setTimeout(updateFrame, 1000); };
    
    // Iniciar captura
    updateFrame();

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
  WiFi.mode(WIFI_AP);
  WiFi.setTxPower(WIFI_POWER_19_5dBm);  // Potencia máxima para mejor alcance
  IPAddress local_ip(192, 168, 4, 1);
  IPAddress gateway(192, 168, 4, 1);
  IPAddress subnet(255, 255, 255, 0);
  WiFi.softAPConfig(local_ip, gateway, subnet);
  WiFi.softAP(ssid, password, 1, 0, 4);  // Canal 1, no oculto, max 4 clientes
  
  delay(500);  // Esperar a que el AP se estabilice antes de iniciar la cámara
  Serial.print("AP IP: ");
  Serial.println(WiFi.softAPIP());
  
  // Inicializar Cámara
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
  config.xclk_freq_hz = 20000000;
  config.frame_size = FRAMESIZE_VGA;
  config.pixel_format = PIXFORMAT_JPEG; 
  config.grab_mode = CAMERA_GRAB_WHEN_EMPTY;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.jpeg_quality = 12;
  config.fb_count = 1;

  if (psramFound()) {
    config.fb_count = 2;
  } else {
    config.frame_size = FRAMESIZE_SVGA;
    config.fb_location = CAMERA_FB_IN_DRAM;
  }

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x\n", err);
    tft.println("Error en Camara!");
  } else {
    startCameraServer();
    tft.println("Camara OK");
  }

  delay(300);  // Dar tiempo al stack Wi-Fi tras la cámara

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
      if(cmd >= 1 && cmd <= 5) {
        bool state = doc["state"];
        sendCommand(cmd, state);
      } else if (cmd == 6) {
        const char* text = doc["text"];
        sendCommand(cmd, false, text);
      }
    }
  });

  server.begin();
}

void loop() {
  delay(100);
}
