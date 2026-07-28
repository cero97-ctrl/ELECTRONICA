#include <Arduino.h>
#include <WiFi.h>
#include <ESPAsyncWebServer.h>
#include <LittleFS.h>
#include <ArduinoJson.h>
#include <TM1637Display.h>
#include <Adafruit_NeoPixel.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>
#include <esp_now.h>


#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1
Adafruit_SSD1306 displayOLED(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Configuración del Access Point
const char* ssid = "Laboratorio ESP32";
const char* password = "esp32123";

// Estructura para mensajes ESP-NOW
typedef struct struct_message {
  uint8_t cmdType; // 1:Red, 2:Green, 3:Blue, 4:Yellow, 5:Relay, 6:OLED
  bool state;
  char text[32];
} struct_message;

struct_message incomingReadings;


// Definición de Pines confirmados
#define PIN_LED_RED 1
#define PIN_LED_GREEN 23
#define PIN_LED_BLUE 19
#define PIN_LED_YELLOW 3
#define PIN_RELAY 0
#define PIN_BUZZER 12

#define PIN_TM_CLK 27
#define PIN_TM_DIO 14
#define PIN_MATRIX 13
#define NUMPIXELS 16

#define PIN_TRIG 15
#define PIN_ECHO 2
#define PIN_LDR 35
#define PIN_TEMP 4
#define PIN_POT 36
#define PIN_TILT 39

AsyncWebServer server(80);
TM1637Display display(PIN_TM_CLK, PIN_TM_DIO);
Adafruit_NeoPixel strip(NUMPIXELS, PIN_MATRIX, NEO_GRB + NEO_KHZ800);
OneWire oneWire(PIN_TEMP);
DallasTemperature sensors(&oneWire);

// Funciones para sensores
float readDistance() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);
  long duration = pulseIn(PIN_ECHO, HIGH, 30000); // Timeout 30ms
  if (duration == 0) return -1;
  return duration * 0.034 / 2;
}

int readLight() {
  return analogRead(PIN_LDR); // 0 a 4095
}

float readTemperature() {
  sensors.requestTemperatures();
  float tempC = sensors.getTempCByIndex(0);
  if (tempC == DEVICE_DISCONNECTED_C) {
    return -127.0;
  }
  return tempC;
}

// Callback cuando se reciben datos vía ESP-NOW
void OnDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  if (len != sizeof(incomingReadings)) return;
  memcpy(&incomingReadings, incomingData, sizeof(incomingReadings));
  
  if (incomingReadings.cmdType == 1) digitalWrite(PIN_LED_RED, incomingReadings.state ? HIGH : LOW);
  else if (incomingReadings.cmdType == 2) digitalWrite(PIN_LED_GREEN, incomingReadings.state ? HIGH : LOW);
  else if (incomingReadings.cmdType == 3) digitalWrite(PIN_LED_BLUE, incomingReadings.state ? HIGH : LOW);
  else if (incomingReadings.cmdType == 4) digitalWrite(PIN_LED_YELLOW, incomingReadings.state ? HIGH : LOW);
  else if (incomingReadings.cmdType == 5) digitalWrite(PIN_RELAY, incomingReadings.state ? HIGH : LOW);
  else if (incomingReadings.cmdType == 6) {
    displayOLED.clearDisplay();
    displayOLED.setCursor(0, 0);
    displayOLED.print(incomingReadings.text);
    displayOLED.display();
  }
}


void setup() {
  Serial.begin(115200);

  // Inicializar Pines Específicos
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);
  pinMode(PIN_LED_BLUE, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_BUZZER, OUTPUT);
  pinMode(PIN_TILT, INPUT);

  // Inicializar sensor de temperatura DS18B20
  sensors.begin();

  // Inicializar Pantalla OLED (SDA: 21, SCL: 22)
  Wire.begin(21, 22);
  if(displayOLED.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    displayOLED.clearDisplay();
    displayOLED.setTextSize(1);
    displayOLED.setTextColor(SSD1306_WHITE);
    displayOLED.setCursor(0, 0);
    displayOLED.println("Iniciando...");
    displayOLED.display();
  } else {
    Serial.println("Error iniciando OLED");
  }

  // Apagar LEDs básicos
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_LED_GREEN, LOW);
  digitalWrite(PIN_LED_BLUE, LOW);
  digitalWrite(PIN_LED_YELLOW, LOW);
  digitalWrite(PIN_RELAY, LOW);
  digitalWrite(PIN_BUZZER, LOW);

  // Inicializar y apagar Matriz WS2812
  strip.begin();
  strip.clear();
  strip.show();

  // Inicializar y apagar Display 7 Segmentos
  display.setBrightness(0x0f);
  display.clear();

  // Iniciar LittleFS
  if (!LittleFS.begin(true)) {
    Serial.println("Error montando LittleFS");
    return;
  }

  // Iniciar AP Mode (Fijado en Canal 1 para ESP-NOW)
  Serial.println("Iniciando Access Point...");
  WiFi.mode(WIFI_AP);
  IPAddress local_ip(192, 168, 4, 2);
  IPAddress gateway(192, 168, 4, 2);
  IPAddress subnet(255, 255, 255, 0);
  WiFi.softAPConfig(local_ip, gateway, subnet);
  WiFi.softAP(ssid, password, 1);
  Serial.print("Dirección IP: ");
  Serial.println(WiFi.softAPIP());

  // Inicializar ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error inicializando ESP-NOW");
  } else {
    esp_now_register_recv_cb(OnDataRecv);
    Serial.println("ESP-NOW Iniciado Correctamente");
  }
  Serial.print("Dirección IP: ");
  Serial.println(WiFi.softAPIP());

  // Mostrar info de red en OLED
  displayOLED.clearDisplay();
  displayOLED.setCursor(0, 0);
  displayOLED.println("WiFi ESP32 Lab");
  displayOLED.println("----------------");
  displayOLED.print("Red:  "); displayOLED.println(ssid);
  displayOLED.print("Pass: "); displayOLED.println(password);
  displayOLED.print("IP:   "); displayOLED.println(WiFi.softAPIP());
  displayOLED.display();

  // Servir archivos estáticos
  server.serveStatic("/", LittleFS, "/").setDefaultFile("index.html");

  // Endpoint: Obtener estado de sensores
  server.on("/api/sensors", HTTP_GET, [](AsyncWebServerRequest *request){
    StaticJsonDocument<200> doc;
    doc["distance"] = readDistance();
    doc["light"] = readLight();
    doc["temperature"] = readTemperature();
    doc["tilt"] = digitalRead(PIN_TILT);
    doc["pot"] = analogRead(PIN_POT);
    
    String response;
    serializeJson(doc, response);
    request->send(200, "application/json", response);
  });

  // Endpoint: Control de actuadores (LEDS básicos)
  server.on("/api/actuators", HTTP_POST, [](AsyncWebServerRequest *request){
    // Manejado en el body handler
  }, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total){
    StaticJsonDocument<200> doc;
    DeserializationError error = deserializeJson(doc, (const char*)data, len);
    
    if (error) {
      request->send(400, "application/json", "{\"status\":\"error\"}");
      return;
    }

    if (doc.containsKey("red")) {
      // Como PIN_LED_RED es 1 (TX), desactivar prints no es estrictamente necesario 
      // si usamos digitalWrite, pero detiene el Serial out.
      digitalWrite(PIN_LED_RED, doc["red"] ? HIGH : LOW);
    }
    if (doc.containsKey("green")) digitalWrite(PIN_LED_GREEN, doc["green"] ? HIGH : LOW);
    if (doc.containsKey("blue")) digitalWrite(PIN_LED_BLUE, doc["blue"] ? HIGH : LOW);
    if (doc.containsKey("yellow")) digitalWrite(PIN_LED_YELLOW, doc["yellow"] ? HIGH : LOW);
    if (doc.containsKey("relay")) digitalWrite(PIN_RELAY, doc["relay"] ? HIGH : LOW);
    if (doc.containsKey("buzzer")) digitalWrite(PIN_BUZZER, doc["buzzer"] ? HIGH : LOW);
    
    request->send(200, "application/json", "{\"status\":\"ok\"}");
  });

  // Endpoint: Control de Display 7 Segmentos
  server.on("/api/display", HTTP_POST, [](AsyncWebServerRequest *request){
    request->send(200, "application/json", "{\"status\":\"ok\"}");
  }, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total){
    StaticJsonDocument<200> doc;
    if (!deserializeJson(doc, (const char*)data, len)) {
      if (doc.containsKey("number")) {
        display.showNumberDec(doc["number"].as<int>(), false);
      } else if (doc.containsKey("clear") && doc["clear"] == true) {
        display.clear();
      }
    }
  });

  // Endpoint: Control de Matriz NeoPixel
  server.on("/api/matrix", HTTP_POST, [](AsyncWebServerRequest *request){
    request->send(200, "application/json", "{\"status\":\"ok\"}");
  }, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total){
    static char bodyBuf[512];
    
    if (index + len > sizeof(bodyBuf) - 1) return;
    memcpy(bodyBuf + index, data, len);
    
    // Procesar cuando llegue el último fragmento
    if (index + len == total) {
      bodyBuf[total] = '\0';
      DynamicJsonDocument doc(2048);
      if (deserializeJson(doc, bodyBuf, total)) return;
      
      if (doc.containsKey("clear") && doc["clear"] == true) {
        strip.clear();
      } else if (doc.containsKey("pixels")) {
        JsonArray pixels = doc["pixels"].as<JsonArray>();
        for (int i = 0; i < NUMPIXELS && i < (int)pixels.size(); i++) {
          JsonArray c = pixels[i].as<JsonArray>();
          strip.setPixelColor(i, strip.Color(c[0].as<uint8_t>(), c[1].as<uint8_t>(), c[2].as<uint8_t>()));
        }
      } else if (doc.containsKey("r") && doc.containsKey("g") && doc.containsKey("b")) {
        uint8_t r = doc["r"];
        uint8_t g = doc["g"];
        uint8_t b = doc["b"];
        for(int i=0; i<NUMPIXELS; i++) {
          strip.setPixelColor(i, strip.Color(r, g, b));
        }
      }
      strip.show();
    }
  });

  // Endpoint: Control de OLED
  server.on("/api/oled", HTTP_POST, [](AsyncWebServerRequest *request){
    request->send(200, "application/json", "{\"status\":\"ok\"}");
  }, NULL, [](AsyncWebServerRequest *request, uint8_t *data, size_t len, size_t index, size_t total){
    StaticJsonDocument<200> doc;
    if (!deserializeJson(doc, (const char*)data, len)) {
      if (doc.containsKey("text")) {
        displayOLED.clearDisplay();
        displayOLED.setCursor(0, 0);
        displayOLED.print(doc["text"].as<String>());
        displayOLED.display();
      } else if (doc.containsKey("clear") && doc["clear"] == true) {
        displayOLED.clearDisplay();
        displayOLED.display();
      }
    }
  });

  server.begin();
  Serial.println("Servidor Web iniciado");
}

void loop() {
  // ESPAsyncWebServer maneja las peticiones en segundo plano.
  // Aquí podríamos añadir lógica para los "Mini-juegos" si decidimos que 
  // la lógica corra en el ESP32, pero por ahora se controlará desde la Web (JS).
}
