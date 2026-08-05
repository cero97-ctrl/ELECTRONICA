# SOLANA — Servicio x402 (pay-per-use)

Servicio **HTTP 402** (paywall): el cliente paga **USDC en Solana** y un agente de
IA responde. Es el foco de ingresos del proyecto (ver
`docs/progreso.md` y `directives/matriz_delegacion_x402.yaml`).

## Arquitectura de 3 capas aplicada

| Capa | Dónde | Qué |
| :--- | :--- | :--- |
| Directiva | `directives/matriz_delegacion_x402.yaml` | qué delegar y con qué guardarraíles |
| Orquestación | `app/main.py` | flujo 402: checkout → firma → verificación → agente |
| Ejecución | `app/{paywall,rpc,verify,replay_store,circuit_breaker,agent}` | piezas deterministas |

## Flujo

1. `POST /v1/agent-task` sin pago → **402** con cabeceras:
   `X-Solana-Amount`, `X-Solana-Token`, `X-Solana-Destination`, `X-Solana-Expires`.
2. El cliente paga USDC y reintenta añadiendo:
   `X-Solana-Signature` (firma Ed25519 base58), `X-Solana-From`, `X-Solana-Expires`.
3. El servicio verifica, en orden:
   - vigencia del checkout,
   - **anti-replay** (misma firma no se cobra 2 veces; TTL 24 h),
   - firma Ed25519 sobre el mensaje canónico (`app/paywall.canonical_message`),
   - pago **on-chain `finalized`** con monto esperado al destino
     (`app/rpc.await_payment`, compara `pre/postTokenBalances`),
   - **circuit breaker** (>3 fallos pausa los cobros).
4. El agente (Clase B, Nivel 1 supervisado) genera el resultado con
   `reviewed=False`: la entrega final requiere revisión humana.

## Ejecutar

```bash
# desde Proyectos/SOLANA
uvicorn x402_service.app.main:app --reload --port 8000
# o
python3 -m uvicorn x402_service.app.main:app --port 8000
```

Dependencias mínimas (`pip install -r x402_service/requirements.txt`):
`fastapi, uvicorn, pydantic, pynacl, httpx, tenacity`; `redis` es opcional.

## Configuración (`.env` del proyecto)

| Variable | Uso |
| :--- | :--- |
| `SOLANA_NETWORK` | `devnet` |
| `SOLANA_RPC_URL` | RPC devnet (verificación de pagos) |
| `SOLANA_WALLET_ADDRESS` | destino del cobro USDC |
| `LLM_API_KEY` | key de Groq/OpenRouter (si falta, responde `[mock]`) |
| `LLM_MODEL` / `LLM_PROVIDER` | modelo y proveedor del agente |
| `REDIS_URL` | opcional; sin ella, anti-replay en memoria (solo dev) |

## Tests (sin red)

```bash
python3 x402_service/tests/test_paywall.py
# o
python -m pytest x402_service/tests -v
```

## Estado

- Esqueleto funcional: flujo 402 completo, verificación finalized, anti-replay,
  circuit breaker y agente con fallback mock. **En devnet, sin fondos todavía.**
- Pendiente para producción: Redis real, suite de tests de integración con RPC,
  revisión humana (Nivel 1), límite diario y whitelist de destino por código,
  despliegue (Docker + reverse proxy TLS).
