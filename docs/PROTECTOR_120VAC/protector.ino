/*
 * PROTECTOR DE VOLTAJE 120VAC - V2.0
 * Microcontrolador: ATtiny85
 * Reloj interno: 1MHz o 8MHz
 */

// ================= DEFINICIÓN DE PINES =================
const int PIN_LED_NORM = 0; // PB0 - LED Verde (Voltaje Normal)
const int PIN_LED_FAIL = 1; // PB1 - LED Rojo (Falla por sobre/bajo voltaje)
const int PIN_SENSADO = A1; // PB2 - Entrada Analógica ADC (Sensado de voltaje)
const int PIN_RELAY = 3;    // PB3 - Control del Relé

// ================= CONSTANTES Y UMBRALES ===============
/*
 * Los umbrales ADC van de 0 a 1023 (equivalente de 0V a 5V en el pin).
 * Deberás calibrar estos valores empíricamente según tu divisor de tensión
 * (1M ohm y 10k ohm) y la caída en el diodo rectificador.
 *
 * Por ejemplo, valores hipotéticos:
 */
const int UMBRAL_MAX = 750; // Equivalente aprox. a > 135V RMS
const int UMBRAL_MIN = 400; // Equivalente aprox. a < 90V RMS

// Tiempo de espera de recuperación (en milisegundos)
// 3 minutos = 3 * 60 * 1000 = 180000 ms
const unsigned long TIEMPO_RECUPERACION = 180000UL;

// ================= VARIABLES GLOBALES ==================
bool estadoFalla = true; // Iniciamos en estado de falla por seguridad
unsigned long
    tiempoInicioEstable; // Para llevar la cuenta regresiva sin usar delay()

void setup() {
  // Configuración de los pines de salida
  pinMode(PIN_RELAY, OUTPUT);
  pinMode(PIN_LED_NORM, OUTPUT);
  pinMode(PIN_LED_FAIL, OUTPUT);

  // Configuración del pin analógico
  pinMode(PIN_SENSADO, INPUT);

  // Estado inicial de seguridad: Carga desconectada
  digitalWrite(PIN_RELAY, LOW);
  digitalWrite(PIN_LED_NORM, LOW);
  digitalWrite(PIN_LED_FAIL, HIGH); // LED rojo encendido

  // Iniciamos el temporizador
  tiempoInicioEstable = millis();
}

void loop() {
  // 1. Leer voltaje de la red rectificado
  int lecturaADC = analogRead(PIN_SENSADO);

  // 2. Evaluar la lectura contra los límites de seguridad
  if (lecturaADC > UMBRAL_MAX || lecturaADC < UMBRAL_MIN) {
    // --- CONDICIÓN DE FALLA ---
    estadoFalla = true;

    // Al ocurrir o mantenerse la falla, reiniciamos continuamente el cronómetro
    tiempoInicioEstable = millis();

    // Acciones de aislamiento inmediato
    digitalWrite(PIN_RELAY, LOW);
    digitalWrite(PIN_LED_NORM, LOW);
    digitalWrite(PIN_LED_FAIL, HIGH);

  } else {
    // --- VOLTAJE DENTRO DE RANGO NORMAL ---
    // Si estábamos en falla, evaluamos si ya pasó el tiempo seguro
    if (estadoFalla) {
      if (millis() - tiempoInicioEstable >= TIEMPO_RECUPERACION) {
        estadoFalla = false;              // Ha superado el tiempo de seguridad
        digitalWrite(PIN_RELAY, HIGH);    // Encender Relé (Acoplar carga)
        digitalWrite(PIN_LED_FAIL, LOW);  // Apagar LED de falla
        digitalWrite(PIN_LED_NORM, HIGH); // Encender LED Normal
      }
    }
  }
}