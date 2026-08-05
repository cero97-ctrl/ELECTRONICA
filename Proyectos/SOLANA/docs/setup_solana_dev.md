# SOLANA — Setup de Desarrollo (Inicio)

> Generado el 2026-08-05. Ejecución paso a paso de la **Lista de Verificación Inicial**
> (analisis.tex §7). Este documento NO pertenece al workspace ELECTRONICA; es material
> propio del proyecto SOLANA.

---

## Estado de la herramienta de desarrollo

| Herramienta | Versión | Estado |
| :--- | :--- | :--- |
| Node.js | v18.19.1 | ✅ instalado |
| npm (prefix usuario `~/.npm-global`) | 9.2.0 | ✅ configurado |
| Python | 3.13.5 (anaconda) | ✅ instalado |
| Rust / Cargo | 1.95.0 | ✅ instalado |
| Git | 2.43.0 | ✅ instalado |
| Solana CLI | 2.1.13 (Agave) | ✅ instalado en `~/.local/share/solana/install/active_release/bin` |
| Anchor (avm) | — | ⏳ compilando en background (`/tmp/avm_install.log`) |
| spl-token | — | pendiente (se instala con `cargo install spl-token-cli` o via Solana toolkit) |

**PATH necesario para Solana CLI (añadir a `~/.bashrc`):**
```bash
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
export PATH="$HOME/.npm-global/bin:$PATH"
export PATH="$HOME/.cargo/bin:$PATH"
```

---

## Paso 1 — Wallet de desarrollo en Devnet ✅

| Dato | Valor |
| :--- | :--- |
| Red configurada | `https://api.devnet.solana.com` (Devnet) |
| Ruta del keypair | `~/.config/solana/id.json` |
| Dirección pública | `AfJT9M8792XYojm45iYFuqDDheLyjP83i85Yujpqyxy6` |
| Balance | 0 SOL (airdrop pendiente) |

**CRÍTICO — Seed phrase** (NO se puede recuperar después): guardada en
`Proyectos/SOLANA/.env` → `SOLANA_DEVNET_SEED_PHRASE` (archivo chmod 600 y excluido de git).
> ⚠️ Esta frase restaura la wallet. Guárdala también en un gestor de contraseñas o en papel,
> offline. No la subas a GitHub ni la compartas con agentes.

### Completar el airdrop (manual, faucet web)
La CLI de Solana está con rate-limit. Usar uno de estos faucets para enviar SOL de prueba a la
dirección `AfJT9M8792XYojm45iYFuqDDheLyjP83i85Yujpqyxy6`:
1. **https://faucet.solana.com** (oficial — pedirá conectar la wallet o pegar la dirección)
2. **https://solfaucet.com**

Tras el airdrop, verificar con:
```bash
solana balance
solana address
```

---

## Paso 2 — Vincular GitHub y X en Superteam Earn (manual)

1. Crear/verificar cuenta de **GitHub** (tu perfil público será tu hoja de vida).
2. Crear/verificar cuenta de **X (Twitter)** con presencia técnica (los revisores de Solana
   suelen verificar la cuenta social).
3. Entrar a **https://earn.superteam.fun** → conectar wallet (Phantom/Backpack) o login con
   GitHub / X.
4. Completar el perfil destacando: *Desarrollador de Agentes de IA, Python, Orquestación de
   Flujos de Trabajo (LLM frameworks), Solana (Devnet)*.

> Nota: Para producción real, la wallet de trabajo será Phantom/Backpack (con su propio seed).
> El keypair de `~/.config/solana/id.json` es para desarrollo/CLI.

---

## Paso 3 — Selección de bounties Development/AI ($200–$800) (manual)

Criterios de filtro en earn.superteam.fun:
- **Categorías:** Development y AI.
- **Rango de pago:** $200–$800 USD (empezar aquí para romper el hielo; los de $5k son competencia dura).
- **Perfil de tarea ideal para ti:**
  - Bots de Telegram/Discord con integración a Solana.
  - Agentes de análisis de datos *on-chain* (fetch RPC, métricas).
  - Integración de SDKs de IA con protocolos DeFi/DePIN.
  - PoC mostrando conexión LLM → Solana.

Guardar 2–3 candidatos y revisar a fondo `Submission Guidelines` antes de comprometerse.

---

## Paso 4 — Estándares de entrega (referencia)

- **Código limpio:** estructura modular, type hints en Python, sin secretos en el repo.
- **Documentación:** README claro (qué hace, cómo ejecutar, requisitos). En Solana se valora
  mucho la calidad del repo de GitHub.
- **Demo:** video corto (Loom/YouTube) de **2 minutos** mostrando el agente en funcionamiento.
- **Revisión previa de errores conocidos** si se genera LaTeX/scripts:
  - `.agent/python.md` (raw strings, jinja2 templates, JSON balanced braces).
  - `.agent/latex.md` (babel es-noshorthands, `\SI{}` con notación `e`).

---

## Siguientes pasos sugeridos

1. Completar el airdrop de SOL devnet (faucet web).
2. Instalar `spl-token-cli` cuando se requiera crear ATAs/tokens de prueba.
3. Confirmar instalación de Anchor (`avm install 0.31.0` + `avm use 0.31.0`) cuando termine la
   compilación en background — solo necesario para programas on-chain en Rust.
4. Ejecutar el paso 2 (Superteam) manualmente y volver con los bounties candidatos.
