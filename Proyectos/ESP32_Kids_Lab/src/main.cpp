#include <Arduino.h>
#include <WiFi.h>
#include <esp_wifi.h>
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

  // Modo Estación (STA) para no crear una red WiFi y evitar interferencias,
  // pero forzamos el canal 1 para poder recibir ESP-NOW del ESP32-S3.
  Serial.println("Iniciando WiFi en Modo Estación...");
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  
  // Forzar el canal WiFi al 1
  esp_wifi_set_promiscuous(true);
  esp_wifi_set_channel(1, WIFI_SECOND_CHAN_NONE);
  esp_wifi_set_promiscuous(false);

  // Inicializar ESP-NOW
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error inicializando ESP-NOW");
  } else {
    esp_now_register_recv_cb(OnDataRecv);
    Serial.println("ESP-NOW Iniciado Correctamente en Canal 1");
  }

  // Mostrar info en OLED
  displayOLED.clearDisplay();
  displayOLED.setCursor(0, 0);
  displayOLED.println("ESP32 Kids Lab");
  displayOLED.println("----------------");
  displayOLED.println("WiFi: OFF");
  displayOLED.println("ESP-NOW: Activado");
  displayOLED.println("Control via ESP32-S3");
  displayOLED.display();

  // (Servidor Web eliminado para evitar interferencias WiFi)
}

void loop() {
  // ESPAsyncWebServer maneja las peticiones en segundo plano.
  // Aquí podríamos añadir lógica para los "Mini-juegos" si decidimos que 
  // la lógica corra en el ESP32, pero por ahora se controlará desde la Web (JS).
}
