#!/usr/bin/env bash
# =============================================================================
# empaquetar_solana.sh — Exporta el proyecto SOLANA para llevarlo a otra PC (USB)
#
# Seguridad:
#   * NUNCA escribe la seed phrase en texto claro dentro del paquete.
#   * Modo por defecto: NO incluye seed ni id.json. La wallet se restaura en la
#     PC nueva desde el gestor de contraseñas con `solana-keygen recover`.
#   * Modo --cifrar: incluye seed e id.json CIFRADOS (AES-256-CBC, openssl) con
#     una contraseña que debes recordar. Si la pierdes, pierdes la wallet.
#
# Uso:
#   ./empaquetar_solana.sh [--cifrar] [--dest /ruta/de/salida]
#
# Salida:
#   <dest>/SOLANA_export_<fecha>.tar.gz
# =============================================================================
set -euo pipefail

PROYECTO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TMP_DIR="$PROYECTO_DIR/.tmp/export_solana"
FECHA="$(date +%F)"
DEST="${HOME}"
CIFRAR=0

# --- Parseo de argumentos ----------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cifrar) CIFRAR=1; shift ;;
    --dest) DEST="${2:?--dest requiere una ruta}"; shift 2 ;;
    *) echo "Opción desconocida: $1"; exit 1 ;;
  esac
done

ENV_FILE="$PROYECTO_DIR/.env"
SOLANA_CONFIG_DIR="$HOME/.config/solana"

# --- Validaciones ------------------------------------------------------------
if [[ "$CIFRAR" == "1" ]]; then
  command -v openssl >/dev/null 2>&1 || { echo "ERROR: openssl no está instalado (necesario para --cifrar)."; exit 1; }
  [[ -f "$ENV_FILE" ]] || { echo "ERROR: no existe $ENV_FILE (no se puede cifrar la seed)."; exit 1; }
fi
[[ -d "$SOLANA_CONFIG_DIR" ]] || echo "AVISO: no se encontró ~/.config/solana ($SOLANA_CONFIG_DIR). Solo se exportará el proyecto."

mkdir -p "$DEST"
rm -rf "$TMP_DIR"
mkdir -p "$TMP_DIR"/{directives,docs,solana_config/cli}

echo "==> Empaquetando SOLANA (fecha $FECHA)"

# 1. Proyecto (directivas + docs) --------------------------------------------
cp -a "$PROYECTO_DIR/directives/." "$TMP_DIR/directives/"
cp -a "$PROYECTO_DIR/docs/." "$TMP_DIR/docs/"

# 2. .env con la seed RELLENABLE (nunca en claro) ------------------------------
if [[ -f "$ENV_FILE" ]]; then
  while IFS= read -r line || [[ -n "$line" ]]; do
    case "$line" in
      SOLANA_DEVNET_SEED_PHRASE=*)
        echo "SOLANA_DEVNET_SEED_PHRASE=# RELLENAR MANUALMENTE con la seed (ver gestor de contraseñas)" ;;
      *) printf '%s\n' "$line" ;;
    esac
  done < "$ENV_FILE" > "$TMP_DIR/.env"
  chmod 600 "$TMP_DIR/.env"
  echo "    [ok] .env con seed redactada"
else
  echo "    [aviso] no existe $ENV_FILE; .env no se exporta"
fi

# 3. Config de Solana (sin id.json a menos que --cifrar) -----------------------
if [[ -f "$SOLANA_CONFIG_DIR/cli/config.yml" ]]; then
  cp -a "$SOLANA_CONFIG_DIR/cli/config.yml" "$TMP_DIR/solana_config/cli/config.yml"
  echo "    [ok] solana cli/config.yml"
fi
if [[ -f "$SOLANA_CONFIG_DIR/install/.version" ]]; then
  cp -a "$SOLANA_CONFIG_DIR/install/.version" "$TMP_DIR/solana_config/install_version.txt"
fi

# 4. Versiones de la toolchain (referencia para reproducir) --------------------
VERS="$TMP_DIR/VERSIONES.txt"
{
  echo "Toolchain detectada en $(hostname) el $FECHA:"
  echo
  for t in "solana --version" "node --version" "npm --version" "rustc --version" "cargo --version" "python3 --version"; do
    printf '%-18s: ' "${t%% *}"
    eval "$t" 2>/dev/null || echo "no instalado"
  done
} > "$VERS" || true
echo "    [ok] VERSIONES.txt"

# 5. Seed e id.json cifrados (solo con --cifrar) -------------------------------
if [[ "$CIFRAR" == "1" ]]; then
  echo -n "Contraseña para cifrar la wallet (debes recordarla): "
  read -rsp '' PW1; echo
  echo -n "Repite la contraseña: "
  read -rsp '' PW2; echo
  [[ "$PW1" == "$PW2" && -n "$PW1" ]] || { echo "ERROR: las contraseñas no coinciden o están vacías."; exit 1; }

  SEED="$(grep -E '^SOLANA_DEVNET_SEED_PHRASE=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '[:space:]')"
  [[ -n "$SEED" ]] || { echo "ERROR: la seed está vacía en .env."; exit 1; }

  echo "$SEED" | openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -pass pass:"$PW1" -a \
    -out "$TMP_DIR/seed.enc"
  chmod 600 "$TMP_DIR/seed.enc"
  echo "    [ok] seed.enc (cifrada, AES-256-CBC)"

  if [[ -f "$SOLANA_CONFIG_DIR/id.json" ]]; then
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 200000 -pass pass:"$PW1" -a \
      -in "$SOLANA_CONFIG_DIR/id.json" -out "$TMP_DIR/id.json.enc"
    chmod 600 "$TMP_DIR/id.json.enc"
    echo "    [ok] id.json.enc (keypair cifrado)"
  fi
fi

# 6. Manual de restauración -----------------------------------------------------
cat > "$TMP_DIR/RESTAURAR_PC_NUEVA.md" <<'MD'
# SOLANA — Restauración en otra PC

Exportado el EXPORT_FECHA. Este paquete NO contiene la seed phrase en texto claro.

## 1. Instalar la toolchain
| Herramienta | Versión de referencia |
| :--- | :--- |
| Node.js | v18.x |
| Python | 3.13.x (anaconda) |
| Rust / Cargo | 1.95.x |
| Solana CLI | 2.1.x (Agave) |

```bash
# Solana CLI (Linux/macOS):
sh -c "$(curl -sSfL https://release.solana.com/2.1.13/install)"

# Restaurar config (ver solana_config/cli/config.yml):
solana config set --url https://api.devnet.solana.com
```

## 2. PATH (añadir a ~/.bashrc)
```bash
export PATH="$HOME/.local/share/solana/install/active_release/bin:$PATH"
export PATH="$HOME/.npm-global/bin:$PATH"
export PATH="$HOME/.cargo/bin:$PATH"
```

## 3. Restaurar la wallet
La seed vive en tu gestor de contraseñas. Restáurala en la PC nueva con:
```bash
solana-keygen recover 'prompt:>'
# pegar la seed phrase cuando la pida; guarda el keypair en ~/.config/solana/id.json
```
Luego verifica:
```bash
solana config set --keypair ~/.config/solana/id.json
solana address        # debe dar AfJT9M8792XYojm45iYFuqDDheLyjP83i85Yujpqyxy6
solana balance        # devnet
```

## 4. Recrear el .env
Copiar `.env` a `Proyectos/SOLANA/.env` y rellenar SOLANA_DEVNET_SEED_PHRASE
manualmente desde el gestor de contraseñas. Luego `chmod 600 .env`.

## 5. Config de Solana exportada
`solana_config/` contiene la config previa (RPC URL, keypair path) como referencia.
Los archivos `.enc` (si existen) solo se descifran con el script `restaurar_cifrado.sh`.

## Seguridad
- No subir `.env`, `seed.enc`, `id.json.enc` ni `~/.config/solana/id.json` a Git.
- Si usaste `--cifrar`, guardar la contraseña en el gestor; sin ella no hay wallet.
- Esta exportación es SOLO devnet. No usar seeds de fondos reales aquí.
MD
sed -i "s/EXPORT_FECHA/$FECHA/" "$TMP_DIR/RESTAURAR_PC_NUEVA.md"
echo "    [ok] RESTAURAR_PC_NUEVA.md"

# 7. Script para descifrar (solo con --cifrar) ----------------------------------
if [[ "$CIFRAR" == "1" ]]; then
  cat > "$TMP_DIR/restaurar_cifrado.sh" <<'SH'
#!/usr/bin/env bash
# Restaura la wallet desde los archivos .enc de este paquete.
set -euo pipefail
command -v openssl >/dev/null 2>&1 || { echo "openssl no instalado"; exit 1; }

echo -n "Contraseña con la que se empaquetó la wallet: "
read -rsp '' PW; echo
[[ -n "$PW" ]] || { echo "Contraseña vacía."; exit 1; }

mkdir -p "$HOME/.config/solana"
if [[ -f "id.json.enc" ]]; then
  openssl enc -d -aes-256-cbc -salt -pbkdf2 -iter 200000 -pass pass:"$PW" -a \
    -in "id.json.enc" -out "$HOME/.config/solana/id.json"
  chmod 600 "$HOME/.config/solana/id.json"
  echo "==> id.json restaurado en ~/.config/solana/id.json"
fi
if [[ -f "seed.enc" ]]; then
  echo "==> Para recuperar la seed en claro (uso manual/offline), ejecuta:"
  echo "    openssl enc -d -aes-256-cbc -salt -pbkdf2 -iter 200000 -pass pass:\"<PW>\" -a -in seed.enc"
fi
solana address 2>/dev/null && echo "==> Wallet lista. Verifica con: solana balance"
SH
  chmod +x "$TMP_DIR/restaurar_cifrado.sh"
  echo "    [ok] restaurar_cifrado.sh"
fi

# 8. Empaquetar -----------------------------------------------------------------
TARBALL="$DEST/SOLANA_export_$FECHA.tar.gz"
tar -C "$TMP_DIR" -czf "$TARBALL" .
echo
echo "=============================================================="
echo "Paquete creado: $TARBALL"
echo
echo "Contenido:"
tar -tzf "$TARBALL" | sed 's/^/  /'
echo
echo "NO incluye (a propósito):"
echo "  * seed phrase en claro"
if [[ "$CIFRAR" == "0" ]]; then
  echo "  * ~/.config/solana/id.json (restaurar con solana-keygen recover desde el gestor)"
fi
echo
echo "Siguiente paso: copia el .tar.gz a un USB y sigue RESTAURAR_PC_NUEVA.md"
echo "  (descomprimir con: tar -xzf SOLANA_export_$FECHA.tar.gz)"
echo "=============================================================="
