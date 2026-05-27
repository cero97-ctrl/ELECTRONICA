/*
 * Circuito de Respuesta Rápida (Quiz Buzzer) - Versión Arduino
 *
 * Este código replica el "enclavamiento" y "bloqueo absoluto" de un
 * circuito basado en tiristores usando lógica de software.
 */

// --- 1. Definición de Pines ---
// Entradas: Botones de los participantes (Normalmente Abiertos a GND)
const int btn1 = 2;
const int btn2 = 3;
const int btn3 = 4;
const int btn4 = 5;

// Entrada: Botón del moderador para reiniciar la ronda
const int btnReset = 6;

// Salidas: LEDs indicadores de cada participante
const int led1 = 8;
const int led2 = 9;
const int led3 = 10;
const int led4 = 11;

// Salida: Zumbador común
const int buzzer = 12;

// --- 2. Variable de Estado Lógico ---
// Esta variable es el equivalente a la red de diodos: crea el "bloqueo
// absoluto"
bool sistemaBloqueado = false;

void setup() {
  // Configurar los pines de los botones usando resistencias Pull-Up internas.
  // Esto mantiene el pin en HIGH por defecto. Al presionar el botón (conectado
  // a GND), leerá LOW.
  pinMode(btn1, INPUT_PULLUP);
  pinMode(btn2, INPUT_PULLUP);
  pinMode(btn3, INPUT_PULLUP);
  pinMode(btn4, INPUT_PULLUP);
  pinMode(btnReset, INPUT_PULLUP);

  // Configurar LEDs y buzzer como salidas
  pinMode(led1, OUTPUT);
  pinMode(led2, OUTPUT);
  pinMode(led3, OUTPUT);
  pinMode(led4, OUTPUT);
  pinMode(buzzer, OUTPUT);
}

void loop() {
  // --- 3. Lógica de Activación y Bloqueo ---
  // Solo evaluamos los botones si el sistema NO ha sido bloqueado previamente
  if (!sistemaBloqueado) {
    if (digitalRead(btn1) == LOW) {
      activarGanador(led1);
    } else if (digitalRead(btn2) == LOW) {
      activarGanador(led2);
    } else if (digitalRead(btn3) == LOW) {
      activarGanador(led3);
    } else if (digitalRead(btn4) == LOW) {
      activarGanador(led4);
    }
  }

  // --- 4. Lógica de Reinicio (Reset) ---
  // El moderador siempre puede reiniciar el sistema, sin importar el estado
  // actual
  if (digitalRead(btnReset) == LOW) {
    digitalWrite(led1, LOW);
    digitalWrite(led2, LOW);
    digitalWrite(led3, LOW);
    digitalWrite(led4, LOW);
    digitalWrite(buzzer, LOW);

    sistemaBloqueado = false; // Liberamos el sistema para la siguiente ronda
    delay(200); // Pequeña pausa anti-rebote (debounce) para el botón
  }
}

// --- Función Auxiliar: Enclavamiento ---
void activarGanador(int pinLed) {
  digitalWrite(pinLed, HIGH); // Enciende la luz del primero que presionó
  digitalWrite(buzzer, HIGH); // Activa el sonido (zumbador activo)
  sistemaBloqueado =
      true; // Se activa el bloqueo absoluto ignorando futuras pulsaciones
}