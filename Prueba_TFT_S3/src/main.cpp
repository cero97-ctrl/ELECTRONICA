#include <Arduino.h>
#include <TFT_eSPI.h>
#include <WiFi.h>
#include <WebServer.h>

// --- CONFIGURACIÓN DEL WiFi (Punto de Acceso) ---
const char* ssid     = "ESP32-S3-TFT";
const char* password = "12345678";  // Mínimo 8 caracteres

// --- OBJETOS ---
TFT_eSPI tft = TFT_eSPI();
WebServer server(80);

// --- PIN BACKLIGHT ---
#define PIN_BLK 21

// --- VARIABLES PARA MENSAJES ---
String mensajeActual = "Esperando mensaje...";
String colorFondo = "negro";
int tamanoTexto = 2;

// --- COLORES DISPONIBLES ---
uint16_t obtenerColor(String nombre) {
  if (nombre == "rojo")     return TFT_RED;
  if (nombre == "verde")    return TFT_GREEN;
  if (nombre == "azul")     return TFT_BLUE;
  if (nombre == "blanco")   return TFT_WHITE;
  if (nombre == "amarillo") return TFT_YELLOW;
  if (nombre == "cyan")     return TFT_CYAN;
  if (nombre == "magenta")  return TFT_MAGENTA;
  if (nombre == "naranja")  return TFT_ORANGE;
  return TFT_BLACK; // negro por defecto
}

// --- MOSTRAR MENSAJE EN LA PANTALLA TFT ---
void mostrarEnPantalla(String mensaje, String fondo, int tamano) {
  uint16_t colorBg = obtenerColor(fondo);
  uint16_t colorTx = (fondo == "blanco" || fondo == "amarillo" || fondo == "cyan") 
                     ? TFT_BLACK : TFT_WHITE;
  
  tft.fillScreen(colorBg);
  tft.setTextColor(colorTx, colorBg);
  tft.setTextSize(tamano);
  tft.setTextWrap(true);
  
  // Dibujar el mensaje con salto de línea automático
  tft.setCursor(5, 10);
  tft.print(mensaje);
  
  // Mostrar información de red en la parte inferior
  tft.setTextSize(1);
  tft.setTextColor(TFT_DARKGREY, colorBg);
  tft.setCursor(5, 260);
  tft.print("WiFi: ");
  tft.print(ssid);
}

// --- PÁGINA WEB HTML ---
const char paginaHTML[] PROGMEM = R"rawliteral(
<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>ESP32-S3 - Control de Pantalla TFT</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body {
      font-family: 'Segoe UI', Arial, sans-serif;
      background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
      min-height: 100vh;
      display: flex;
      justify-content: center;
      align-items: center;
      padding: 20px;
    }
    .container {
      background: rgba(255, 255, 255, 0.08);
      backdrop-filter: blur(20px);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 20px;
      padding: 35px;
      width: 100%;
      max-width: 450px;
      box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
    }
    h1 {
      color: #fff;
      text-align: center;
      font-size: 1.6em;
      margin-bottom: 8px;
    }
    .subtitle {
      color: rgba(255,255,255,0.5);
      text-align: center;
      font-size: 0.85em;
      margin-bottom: 25px;
    }
    .status {
      background: rgba(0, 255, 136, 0.15);
      border: 1px solid rgba(0, 255, 136, 0.3);
      border-radius: 10px;
      padding: 10px 15px;
      margin-bottom: 20px;
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .status .dot {
      width: 10px; height: 10px;
      background: #00ff88;
      border-radius: 50%;
      animation: pulse 2s infinite;
    }
    @keyframes pulse {
      0%, 100% { opacity: 1; }
      50% { opacity: 0.3; }
    }
    .status span { color: #00ff88; font-size: 0.9em; }
    label {
      color: rgba(255,255,255,0.8);
      font-size: 0.9em;
      display: block;
      margin-bottom: 6px;
      margin-top: 15px;
    }
    textarea {
      width: 100%;
      height: 100px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 12px;
      padding: 12px;
      color: #fff;
      font-size: 1em;
      resize: vertical;
      outline: none;
      transition: border 0.3s;
    }
    textarea:focus {
      border-color: #667eea;
    }
    select {
      width: 100%;
      padding: 10px 12px;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.2);
      border-radius: 12px;
      color: #fff;
      font-size: 0.95em;
      outline: none;
      cursor: pointer;
    }
    select option { background: #302b63; color: #fff; }
    .row { display: flex; gap: 12px; }
    .row > div { flex: 1; }
    button {
      width: 100%;
      padding: 14px;
      margin-top: 25px;
      background: linear-gradient(135deg, #667eea, #764ba2);
      color: #fff;
      border: none;
      border-radius: 12px;
      font-size: 1.1em;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.3s;
      letter-spacing: 0.5px;
    }
    button:hover {
      transform: translateY(-2px);
      box-shadow: 0 8px 25px rgba(102, 126, 234, 0.4);
    }
    button:active { transform: translateY(0); }
    .msg-ok {
      background: rgba(0, 255, 136, 0.15);
      border: 1px solid rgba(0, 255, 136, 0.3);
      color: #00ff88;
      padding: 10px;
      border-radius: 10px;
      text-align: center;
      margin-top: 15px;
      display: none;
      font-size: 0.9em;
    }
    .footer {
      color: rgba(255,255,255,0.3);
      text-align: center;
      font-size: 0.75em;
      margin-top: 20px;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>&#128225; Control TFT</h1>
    <p class="subtitle">ESP32-S3 &bull; Pantalla 1.69"</p>
    
    <div class="status">
      <div class="dot"></div>
      <span>Conectado al ESP32-S3</span>
    </div>

    <form id="formMsg" action="/enviar" method="POST">
      <label for="mensaje">Mensaje para la pantalla:</label>
      <textarea id="mensaje" name="mensaje" placeholder="Escribe tu mensaje aqui..." maxlength="200"></textarea>

      <div class="row">
        <div>
          <label for="color">Color de fondo:</label>
          <select id="color" name="color">
            <option value="negro">Negro</option>
            <option value="rojo">Rojo</option>
            <option value="verde">Verde</option>
            <option value="azul">Azul</option>
            <option value="blanco">Blanco</option>
            <option value="amarillo">Amarillo</option>
            <option value="cyan">Cyan</option>
            <option value="magenta">Magenta</option>
            <option value="naranja">Naranja</option>
          </select>
        </div>
        <div>
          <label for="tamano">Tamano texto:</label>
          <select id="tamano" name="tamano">
            <option value="1">Pequeno</option>
            <option value="2" selected>Normal</option>
            <option value="3">Grande</option>
            <option value="4">Muy grande</option>
          </select>
        </div>
      </div>

      <button type="submit">&#128232; Enviar a Pantalla</button>
    </form>

    <div class="msg-ok" id="msgOk">&#9989; Mensaje enviado correctamente</div>

    <p class="footer">WiFi: ESP32-S3-TFT &bull; IP: 192.168.4.1</p>
  </div>

  <script>
    document.getElementById('formMsg').addEventListener('submit', function(e) {
      e.preventDefault();
      var fd = new FormData(this);
      fetch('/enviar', { method: 'POST', body: fd })
        .then(function(r) { return r.text(); })
        .then(function() {
          var ok = document.getElementById('msgOk');
          ok.style.display = 'block';
          setTimeout(function() { ok.style.display = 'none'; }, 3000);
        });
    });
  </script>
</body>
</html>
)rawliteral";

// --- MANEJAR PETICIÓN RAÍZ (página principal) ---
void handleRoot() {
  server.send(200, "text/html", paginaHTML);
}

// --- MANEJAR ENVÍO DE MENSAJE ---
void handleEnviar() {
  if (server.hasArg("mensaje")) {
    mensajeActual = server.arg("mensaje");
    
    if (server.hasArg("color")) {
      colorFondo = server.arg("color");
    }
    if (server.hasArg("tamano")) {
      tamanoTexto = server.arg("tamano").toInt();
      if (tamanoTexto < 1) tamanoTexto = 1;
      if (tamanoTexto > 4) tamanoTexto = 4;
    }
    
    // Mostrar el mensaje en la pantalla TFT
    mostrarEnPantalla(mensajeActual, colorFondo, tamanoTexto);
    
    Serial.print("Mensaje recibido: ");
    Serial.println(mensajeActual);
    Serial.print("Color de fondo: ");
    Serial.println(colorFondo);
    Serial.print("Tamano: ");
    Serial.println(tamanoTexto);
  }
  
  server.send(200, "text/plain", "OK");
}

// --- MANEJAR PÁGINA NO ENCONTRADA ---
void handleNotFound() {
  server.send(404, "text/plain", "Pagina no encontrada");
}

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== ESP32-S3 WiFi + TFT ===");
  
  // --- Inicializar Backlight ---
  pinMode(PIN_BLK, OUTPUT);
  digitalWrite(PIN_BLK, HIGH);
  
  // --- Inicializar pantalla TFT ---
  Serial.println("Inicializando pantalla TFT...");
  tft.init();
  tft.setRotation(0);
  tft.fillScreen(TFT_BLACK);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.setTextSize(2);
  tft.setCursor(5, 10);
  tft.println("Iniciando");
  tft.println("WiFi...");
  Serial.println("Pantalla TFT lista.");
  
  // --- Crear Punto de Acceso WiFi ---
  Serial.println("Creando punto de acceso WiFi...");
  WiFi.softAP(ssid, password);
  delay(500);
  
  IPAddress ip = WiFi.softAPIP();
  Serial.print("Red WiFi: ");
  Serial.println(ssid);
  Serial.print("Contrasena: ");
  Serial.println(password);
  Serial.print("Direccion IP: ");
  Serial.println(ip);
  
  // --- Mostrar info de conexión en la pantalla ---
  tft.fillScreen(TFT_BLACK);
  tft.setTextSize(2);
  tft.setTextColor(TFT_GREEN, TFT_BLACK);
  tft.setCursor(5, 10);
  tft.println("WiFi Listo!");
  tft.println();
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.setTextSize(1);
  tft.println("Red WiFi:");
  tft.setTextSize(2);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.println(ssid);
  tft.println();
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.setTextSize(1);
  tft.println("Contrasena:");
  tft.setTextSize(2);
  tft.setTextColor(TFT_WHITE, TFT_BLACK);
  tft.println(password);
  tft.println();
  tft.setTextColor(TFT_YELLOW, TFT_BLACK);
  tft.setTextSize(1);
  tft.println("Abrir en navegador:");
  tft.setTextSize(2);
  tft.setTextColor(TFT_CYAN, TFT_BLACK);
  tft.println("192.168.4.1");
  
  // --- Configurar servidor web ---
  server.on("/", HTTP_GET, handleRoot);
  server.on("/enviar", HTTP_POST, handleEnviar);
  server.onNotFound(handleNotFound);
  server.begin();
  
  Serial.println("Servidor web iniciado en http://192.168.4.1");
  Serial.println("=== LISTO ===");
}

void loop() {
  server.handleClient();
  delay(2);
}
