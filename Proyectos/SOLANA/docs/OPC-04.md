# OPC-04: Diseño de Arquitectura para un Agente de IA con Pagos en USDC en Solana

¿Cómo diseñar la arquitectura de un Agente de IA que preste servicios pagados por consulta en USDC usando Solana?

Diseñar un agente de IA que preste servicios y cobre en USDC por cada consulta (petición API) en la red de Solana exige combinar tres pilares: **un framework de agentes**, **un middleware de verificación de pagos on-chain** y **la ejecución de la tarea**.

A diferencia de las arquitecturas Web2 tradicionales basadas en suscripciones y tarjetas de crédito, este modelo se basa en la especificación **x402 (HTTP 402 Payment Required)** o en un flujo de **Firma de Transacciones/Verificación de Hash** en tiempo real.

## 🏗️ 1. Arquitectura General del Sistema

El flujo completo consta de tres capas principales:

```text
[ Cliente / Usuario ]
        │
        │ 1. Petición POST /v1/analisis (Sin comprobante)
        ▼
┌──────────────────────────────────────────────────────────┐
│              GATEWAY & PAGO (Middleware)                 │
│  - Devuelve Error HTTP 402 (Monto USDC + Memo / Wallet)  │
└──────────────────────────┬───────────────────────────────┘
                           │
        │ 2. Cliente firma y transmite la transacción en Solana
        │ 3. Petición POST /v1/analisis (Incluye Transaction Signature)
                           ▼
┌──────────────────────────────────────────────────────────┐
│             VERIFICACIÓN Y ORQUESTACIÓN                  │
│  - Solana RPC: Confirma TX on-chain (USDC transfer)      │
│  - Previene "Replay Attacks" (Guarda TX ID en Redis/DB)  │
└──────────────────────────┬───────────────────────────────┘
                           │
        │ 4. Transacción válida confirmada
                           ▼
┌──────────────────────────────────────────────────────────┐
│           AGENTE DE IA & LÓGICA DE NEGOCIO               │
│  - Ejecución de Tareas / Inferencia LLM / Herramientas   │
│  - Respuesta final al Cliente (HTTP 200 OK)              │
└──────────────────────────────────────────────────────────┘
```

## ⚙️ 2. Desglose de Componentes Tecnológicos

| Componente | Tecnología Sugerida | Función |
| :--- | :--- | :--- |
| **API Gateway / Server** | FastAPI (Python) o Express (Node.js) | Maneja los endpoints de entrada, validación de schemas y respuestas de pago. |
| **Blockchain Client / RPC** | Helius, QuickNode o Alchemy (Solana RPC) | Consulta el estado final (*confirmed/finalized*) de las transacciones USDC. |
| **Capa de Agentes** | LangChain, CrewAI, AutoGen o LlamaIndex | Ejecuta el procesamiento de la IA (análisis, código, inferencias, scraping, etc.). |
| **Caché y Anti-Replay** | Redis | Guarda las firmas de las transacciones exitosas para evitar que una misma transacción se retrace o re-use. |
| **Contrato / Token** | USDC SPL Token (`EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v`) | El token SPL de USDC oficial en la red principal (*mainnet-beta*) de Solana. |

## 🔄 3. El Flujo de Trabajo (Paso a Paso)

### Paso A: Handshake de Pago (HTTP 402)

1. **Petición del cliente:** El usuario/agente cliente envía una solicitud para consumir un servicio:
   `POST /api/v1/agent-task` con el *payload* de entrada.
2. **Respuesta 402 Payment Required:** El servidor responde con el estado HTTP 402 solicitando el pago e indicando las instrucciones:

```json
{
  "status": 402,
  "message": "Payment Required",
  "payment_details": {
    "recipient_wallet": "7xKX...SolanaWalletAddress",
    "amount_usdc": 0.10,
    "usdc_mint": "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "memo": "task_id_8921a9"
  }
}
```

### Paso B: Transferencia de USDC en Solana

1. El cliente ejecuta una transferencia SPL de **0.10 USDC** a la billetera del agente.
2. El cliente añade un instruccional de **Memo** en la misma transacción (`task_id_8921a9`) para vincular la transacción a la consulta.
3. Solana confirma la transacción en **~400 milisegundos**.

### Paso C: Verificación y Ejecución

1. El cliente vuelve a enviar la solicitud a la API del Agente, esta vez agregando en los encabezados la firma de la transacción:
   `Header: X-Solana-Signature: 5Kz9...TX_HASH`
2. El middleware de la API realiza tres validaciones críticas:
   * **Inmutable / Unicidad:** Verifica en Redis que el `TX_HASH` no haya sido procesado previamente.
   * **Confirmación On-Chain:** Consulta al RPC de Solana que la transacción esté en estado `confirmed` o `finalized`.
   * **Monto y Destino:** Valida que el receptor sea la wallet de la OPC, la cantidad sea $\ge 0.10$ USDC y el mint sea el contrato oficial de USDC.
3. Si la verificación pasa, guarda el `TX_HASH` en Redis y transmite la consulta a la **Capa de Orquestación del Agente de IA**.
4. El agente genera el resultado y el API responde con HTTP 200 conteniendo la respuesta de la IA.

## 🛡️ 4. Consideraciones Clave de Seguridad y Eficiencia

1. **Protección Anti-Replay (Doble Gasto):** Es indispensable usar una base de datos en memoria (como Redis) con expiración para registrar las transacciones procesadas. Si dos peticiones usan la misma firma de transacción, la segunda debe ser rechazada inmediatamente.
2. **Tiempos de Espera (Timeouts):** Dado que Solana confirma bloques en menos de 1 segundo, la validación del hash tarda milisegundos. Sin embargo, para evitar retrasos de los RPCs públicos, es imprescindible usar proveedores RPC dedicados (como **Helius** o **QuickNode**).
3. **Manejo de Errores del Agente:** Si la transacción de pago en USDC fue válida pero el agente falla en su ejecución interna (por ejemplo, timeout de un modelo LLM), el sistema debe:
   * Registrar el fallo.
   * Emitir un *credit token* interno o reembolsar/re-intentar la consulta sin exigir un nuevo pago.
4. **Agrupación de Fondos (Sweeping):** Las tarifas recibidas en la wallet receptora se acumulan en la cuenta asociada de tokens (ATA) de USDC. El agente puede tener una tarea programada (*cron job*) para mover periódicamente las ganancias acumuladas a una wallet fría de la OPC o a un protocolo de rendimiento DeFi.

## 💻 5. Ejemplo de Código: Middleware de Validación (Python / FastAPI)

```python
from fastapi import FastAPI, Header, HTTPException, status
from solana.rpc.api import Client
from redis import Redis

app = FastAPI()
solana_client = Client("https://mainnet.helius-rpc.com/?api-key=TU_API_KEY")
redis_db = Redis(host='localhost', port=6379, db=0)

RECIPIENT_WALLET = "7xKX...SolanaWalletAddress"
EXPECTED_USDC_AMOUNT_LAMPORTS = 100_000  # 0.10 USDC (USDC usa 6 decimales)

@app.post("/v1/agent-task")
async def execute_agent_task(payload: dict, x_solana_signature: str = Header(None)):
    # 1. Si no hay firma, exigir pago (HTTP 402)
    if not x_solana_signature:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "Payment required to execute AI task.",
                "recipient": RECIPIENT_WALLET,
                "amount_usdc": 0.10
            }
        )

    # 2. Prevenir Replay Attacks
    if redis_db.exists(x_solana_signature):
        raise HTTPException(status_code=400, detail="Transaction signature already used.")

    # 3. Validar la transacción en la Blockchain
    tx_info = solana_client.get_transaction(x_solana_signature, max_supported_transaction_version=0)
    if not tx_info or not tx_info.get("result"):
        raise HTTPException(status_code=400, detail="Transaction not found or not confirmed yet.")

    # (Añadir lógica para verificar que los balances modificados coincidan con el pago recibido)

    # 4. Registrar la firma para evitar reutilización
    redis_db.setex(x_solana_signature, 86400, "processed")  # Guardar por 24 horas

    # 5. Ejecutar la lógica del Agente de IA
    response = run_ai_agent_pipeline(payload)
    return {"status": "success", "data": response}

def run_ai_agent_pipeline(payload):
    # Lógica de LangChain / CrewAI / LlamaIndex
    return "Resultado procesado por el Agente de IA."
```
