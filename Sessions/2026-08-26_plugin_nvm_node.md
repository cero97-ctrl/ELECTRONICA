# Sesión 2026-08-26 — Plugin nvm-env.js (Node moderno en shells de opencode)

## Tema
Diagnóstico de la instalación de Node.js en el entorno y creación del plugin hermano `nvm-env.js` para que las shells de opencode usen Node vía nvm.

## Actividades
1. Diagnóstico: `node` resolvía a `/usr/bin/node` **v18.19.1** (apt Mint, EOL abr 2025). nvm ya tenía instaladas v20.20.2, v22.23.1 y v24.11.1, pero las shells de opencode no son interactivas (no cargan `.bashrc`/nvm) → ganaba el node 18 del sistema.
2. Impacto evaluado: único proyecto Node es `Proyectos/cloudflare-agent` (wrangler 3.114.17, miniflare engines >=16.13) — funcionaba con 18, pero sin parches de seguridad y con riesgo de `EBADENGINE` al actualizar dependencias.
3. Verificado sin conflicto de nombres: ni `elect_env` ni la base anaconda traen `node` en su `bin`, así que el nuevo plugin no compite con `conda-env.js`.
4. Creación de `.opencode/plugins/nvm-env.js` (export `NvmEnvPlugin`, hook `shell.env`, patrón defensivo idéntico a `conda-env.js`): antepone `~/.nvm/versions/node/v22.23.1/bin` al PATH; fallback determinista a la mayor versión instalada si la fijada desaparece; hook inactivo + warning si no hay ninguna.
5. Verificación local (vía copias `.mjs` en `/tmp/opencode`, porque el node 18 trata `.js` como CommonJS; opencode carga los plugins con su propio runtime, igual que hace con `conda-env.js`):
   - Sintaxis OK (`node --check`).
   - Hook OK: PATH resultante `~/.nvm/versions/node/v22.23.1/bin:/...`.
   - Fallback OK: fijando `v99.0.0` → warning + usa v24.11.1.
6. Documentación añadida en `AGENTS.md` ("Node vía nvm en shells de opencode"), análoga a la línea del plugin conda.

## Decisiones
- Versión fijada: **v22.23.1** (LTS hasta abr 2027), elegida por el usuario entre v22 / v24 / dinámica; recomendada por compatibilidad del ecosistema y wrangler ya presente bajo esa versión.
- Plugin hermano separado (`nvm-env.js`) en vez de extender `conda-env.js`: una responsabilidad por plugin.
- El node 18 del sistema queda intacto como reserva (solo pierde el PATH dentro de opencode).

## Pendientes
- **Reiniciar opencode** para activar el plugin (los plugins solo cargan al arranque).
- Tras el reinicio, verificar en shell real: `which node && node --version` → debe apuntar a `~/.nvm/.../v22.23.1/bin/node`; opcionalmente `npx wrangler --version` en `Proyectos/cloudflare-agent`.
- Solo si aparecieran warnings `EBADENGINE`: regenerar `node_modules` de cloudflare-agent (no esperado).
