# SOLANA — Progreso del Proyecto

> Bitácora de avance. Actualizada el 2026-08-05.
> Objetivo principal: **generar ingresos como desarrollador en la blockchain de Solana**,
> empezando de forma individual y delegando tareas repetitivas a agentes de IA de manera
> gradual y segura (ver `directives/matriz_delegacion_x402.yaml`).

---

## 📊 Resumen de estado

| Área | Estado |
| :--- | :--- |
| Estudio inicial (OPC-01 a OPC-08 + analisis.tex) | ✅ completado |
| Directiva de delegación por riesgo (x402) | ✅ creada (`directives/matriz_delegacion_x402.yaml`) |
| Toolchain (Solana CLI) | ✅ instalado |
| Wallet de desarrollo (Devnet) | ✅ generada |
| Airdrop SOL devnet | ⏳ pendiente (rate-limit CLI → faucet web) |
| Anchor / avm | ❌ compilación falló en background (reintentar cuando haga falta) |
| Superteam Earn (perfil) | ⏳ pendiente (manual) |
| Selección de bounties | ⏳ pendiente (manual) |
| Esqueleto servicio x402 | ⏳ pendiente (siguiente gran paso) |

---

## ✅ Hecho hasta ahora

### 1. Estudio y estrategia (docs/OPC-01 a OPC-08, analisis.tex/pdf)
- Serie completa de documentos sobre OPC + Agentes IA + Solana (con apoyo de Gemini).
- Conclusión estratégica adoptada: **empezar trabajando individualmente en Solana**, ganar
  experiencia y delegar a agentes solo cuando el flujo lo requiera, priorizando seguridad.

### 2. Directiva de delegación por riesgo
- Archivo: `directives/matriz_delegacion_x402.yaml` (validado, YAML correcto).
- Clasifica tareas en clases A (sin dinero) → D (dinero irreversible) con niveles 0–3.
- Parámetros calibrados a cobros x402 de $1–50/consulta: límite diario $200, umbral humano $50,
  circuit breaker, anti-replay Redis, confirmación RPC `finalized`.

### 3. Toolchain de desarrollo
| Herramienta | Versión | Ubicación |
| :--- | :--- | :--- |
| Node.js | v18.19.1 | sistema |
| npm | 9.2.0 | prefix `~/.npm-global` |
| Python | 3.13.5 (anaconda) | sistema |
| Rust / Cargo | 1.95.0 | `~/.cargo` |
| Git | 2.43.0 | sistema |
| Solana CLI | 2.1.13 (Agave) | `~/.local/share/solana/install/active_release/bin` |

**PATHs a añadir a `~/.bashrc`:**
```bash
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
export PATH="$HOME/.npm-global/bin:$PATH"
export PATH="$HOME/.cargo/bin:$PATH"
```

### 4. Wallet de desarrollo (Devnet)
- Red configurada: `https://api.devnet.solana.com`
- Keypair: `~/.config/solana/id.json`
- Dirección pública: `AfJT9M8792XYojm45iYFuqDDheLyjP83i85Yujpqyxy6`
- Balance: 0 SOL (airdrop pendiente)
- Seed phrase guardada en `Proyectos/SOLANA/.env` → `SOLANA_DEVNET_SEED_PHRASE`
  (chmod 600, excluida de git vía `.gitignore:3`).
- ⚠️ Se eliminó la seed del `setup_solana_dev.md` para no tenerla en texto plano.

---

## ⏳ Pendiente por hacer

### A corto plazo (para empezar a trabajar)
1. **Airdrop de SOL devnet** (manual, faucet web):
   - https://faucet.solana.com (oficial) o https://solfaucet.com.
   - Destino: `AfJT9M8792XYojm45iYFuqDDheLyjP83i85Yujpqyxy6`.
   - Verificar con `solana balance`.
2. **Registro en Superteam Earn** (manual):
   - Crear/vincular GitHub + X.
   - Entrar a https://earn.superteam.fun, conectar wallet, completar perfil.
   - Detalle completo en `docs/setup_solana_dev.md` → Paso 2.
3. **Selección de 2–3 bounties** Development/AI ($200–$800) (manual).
   - Criterios de filtro en `docs/setup_solana_dev.md` → Paso 3.

### A medio plazo (infraestructura del servicio x402)
4. **Esqueleto del servicio pay-per-use x402** (foco de ingresos):
   - Middleware FastAPI: endpoint `/v1/agent-task`, respuesta HTTP 402.
   - Verificación on-chain vía RPC (Helius/QuickNode) del TX en estado `finalized`.
   - Anti-replay con Redis (TTL 24h).
   - Lógica de agente IA (LangChain/CrewAI/LlamaIndex) — Nivel 1 supervisado.
   - Aplicar `directives/matriz_delegacion_x402.yaml` en el diseño.
5. **Anchor / avm** (solo si se escribe código on-chain en Rust):
   - La compilación en background murió; reinstalar en primer plano cuando haga falta:
     `cargo install --git https://github.com/coral-xyz/anchor avm --locked --force`
     luego `avm install 0.31.0 && avm use 0.31.0`.
   - Alternativa fallida: paquete npm `@coral-xyz/anchor-cli` (deprecated, binario roto).
6. **spl-token-cli**: instalar cuando se requiera crear ATAs/tokens de prueba
   (`cargo install spl-token-cli`).

---

## 📌 Notas y advertencias

- **Seed phrase**: solo en `Proyectos/SOLANA/.env`. Guardar copia offline (gestor de
  contraseñas/papel). No subir a GitHub ni compartir con agentes.
- **Seguridad para mainnet**: nunca poner seeds de fondos reales en `.env`. Usar hardware
  wallet o multisig (Squads Protocol). El `.env` actual es solo para Devnet.
- **Entorno**: ejecutar todo desde la raíz del proyecto SOLANA; no tocar el workspace
  ELECTRONICA (directivas/paso a paso de ELECTRONICA quedan intactos).
- **Estado del airdrop devnet**: la CLI de Solana está con rate-limit temporal; los faucets web
  son la vía para completarlo.
