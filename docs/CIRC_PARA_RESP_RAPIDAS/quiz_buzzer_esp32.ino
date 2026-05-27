/*
 * Circuito de Respuesta Rápida (Quiz Buzzer) - Versión ESP32 con Servidor Web
 *
 * Este código adapta la lógica de enclavamiento al ESP32 e implementa
 * un pequeño servidor web para mostrar al ganador en una red local.
 */

#include <WebServer.h>
#include <WiFi.h>

// --- Configuración de Red Wi-Fi ---
const char *ssid = "TU_RED_WIFI";
const char *password = "TU_CONTRASENA";

// Inicializar el servidor web en el puerto 80
WebServer server(80);

// --- 1. Definición de Pines (Según Esquema ESP32) ---
const int btn1 = 12;
const int btn2 = 14;
const int btn3 = 27;
const int btn4 = 26;
const int btnReset = 33;

const int led1 = 15;
const int led2 = 2;
const int led3 = 0;
const int led4 = 4;
const int buzzer = 5;

// --- 2. Variables de Estado ---
bool sistemaBloqueado = false;
String ganador = "Esperando respuesta...";

// --- 3. Generación de la Página Web ---
void handleRoot() {
  String html =
      "<!DOCTYPE html><html lang=\"es\"><head><meta charset=\"UTF-8\">";
  html += "<meta name=\"viewport\" content=\"width=device-width, "
          "initial-scale=1.0\">";
  html += "<title>Marcador - Quiz Buzzer</title>";
  // Estilos CSS básicos
  html += "<style>body{font-family: Arial, sans-serif; text-align: center; "
          "margin-top: 15%; background-color: #f4f4f4;} ";
  html += "h1{color: #333; font-size: 2.5em;} h2{color: #d9534f; font-size: "
          "4em;}</style>";
  // Refrescar automáticamente la página cada segundo
  html += "<meta http-equiv=\"refresh\" content=\"1\">";
  html += "</head><body>";
  html += "<h1>Competencia de Conocimiento</h1>";
  html += "<h2>" + ganador + "</h2>";
  html += "</body></html>";

  server.send(200, "text/html", html);
}

void setup() {
  Serial.begin(115200);

  // Configurar las resistencias Pull-Up internas
  pinMode(btn1, INPUT_PULLUP);
  pinMode(btn2, INPUT_PULLUP);
  pinMode(btn3, INPUT_PULLUP);
  pinMode(btn4, INPUT_PULLUP);
  pinMode(btnReset, INPUT_PULLUP);

  pinMode(led1, OUTPUT);
  pinMode(led2, OUTPUT);
  pinMode(led3, OUTPUT);
  pinMode(led4, OUTPUT);
  pinMode(buzzer, OUTPUT);

  // Conexión Wi-Fi
  Serial.print("Conectando a ");
  Serial.println(ssid);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println(
      "\nWiFi conectado. Puedes ver el marcador en la Dirección IP: ");
  Serial.println(WiFi.localIP());

  // Configurar y arrancar servidor web
  server.on("/", handleRoot);
  server.begin();
}

void loop() {
  // Atender peticiones del servidor web (Navegadores)
  server.handleClient();

  // --- 4. Lógica de Activación y Bloqueo ---
  if (!sistemaBloqueado) {
    if (digitalRead(btn1) == LOW) {
      activarGanador(led1, "¡Participante 1!");
    } else if (digitalRead(btn2) == LOW) {
      activarGanador(led2, "¡Participante 2!");
    } else if (digitalRead(btn3) == LOW) {
      activarGanador(led3, "¡Participante 3!");
    } else if (digitalRead(btn4) == LOW) {
      activarGanador(led4, "¡Participante 4!");
    }
  }

  // --- 5. Lógica de Reinicio (Reset) ---
  if (digitalRead(btnReset) == LOW) {
    digitalWrite(led1, LOW);
    digitalWrite(led2, LOW);
    digitalWrite(led3, LOW);
    digitalWrite(led4, LOW);
    digitalWrite(buzzer, LOW);

    ganador = "Esperando respuesta...";
    sistemaBloqueado = false;
    delay(200); // Pequeña pausa anti-rebote
  }
}

// --- Función Auxiliar: Enclavamiento ---
void activarGanador(int pinLed, String nombreGanador) {
  digitalWrite(pinLed, HIGH);
  digitalWrite(buzzer, HIGH);
  ganador = nombreGanador;
  sistemaBloqueado = true;
}