#!/usr/bin/env python3
"""test_extraer_repo.py — Tests deterministas (0 créditos) de
execution/extraer_repo_github.py (Fase 1b repo→skill).

Cubre las funciones puras de filtrado y extracción: `_es_url_github`,
`_nombre_repo_de_url`, `_archivos_en_directorio`, `_deberia_incluir` y
`_concatenar_archivos`. No necesita red, git ni API.
"""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "execution"))

from extraer_repo_github import (  # noqa: E402
    _archivos_en_directorio,
    _concatenar_archivos,
    _deberia_incluir,
    _es_url_github,
    _nombre_repo_de_url,
)

from validar_skill_formulas import (  # noqa: E402
    _escaneo_peligro_sistema,
    _escaneo_seguridad,
    _extraer_bloques,
)

FALLOS = []


def check(nombre, cond, detalle=""):
    tag = "OK " if cond else "FAIL"
    print(f"[{tag}] {nombre}" + (f" — {detalle}" if detalle and not cond else ""))
    if not cond:
        FALLOS.append(nombre)


# ── `_es_url_github` ──────────────────────────────────────────────────────────

check("https URL github detectada", _es_url_github("https://github.com/foo/bar"))
check("git@ ssh URL github detectada", _es_url_github("git@github.com:foo/bar.git"))
check("ruta local NO es github", not _es_url_github("/home/user/mirepo"))
check("url no-github NO es github", not _es_url_github("https://gitlab.com/foo/bar"))


# ── `_nombre_repo_de_url` ─────────────────────────────────────────────────────

check("nombre de https sin .git", _nombre_repo_de_url("https://github.com/psf/requests") == "psf-requests")
check("nombre de https con .git", _nombre_repo_de_url("https://github.com/a/b.git") == "a-b")
check("nombre de git@ ssh", _nombre_repo_de_url("git@github.com:owner/repo.git") == "owner-repo")


# ── `_deberia_incluir`: extensiones y globs ──────────────────────────────────

exts = {".py", ".md", ".txt"}
sim = lambda rel, nombre: SimpleNamespace(name=nombre, suffix=Path(rel).suffix,
                                          relative_to=lambda _p: Path(rel))
# NOTE: _deberia_incluir recibe un Path real, no SimpleNamespace; construir Path.

def mk(rel):
    # Devuelve un Path fake con relative_to que devuelve la ruta relativa.
    return _PathStub(rel)

class _PathStub:
    def __init__(self, rel):
        self.rel = rel
        self.name = Path(rel).name
        self.suffix = Path(rel).suffix
    def relative_to(self, other):
        return Path(self.rel)

ok1, _ = _deberia_incluir(mk("src/app.py"), exts, None, None, Path("."))
check("archivo .py incluido", ok1)
ok2, _ = _deberia_incluir(mk("README.md"), exts, None, None, Path("."))
check("archivo .md incluido", ok2)
ok3, _ = _deberia_incluir(mk("img/logo.png"), exts, None, None, Path("."))
check("archivo .png excluido (extensión no permitida)", not ok3)

ok4, _ = _deberia_incluir(mk("src/app.py"), exts, ["*.md"], None, Path("."))
check("--incluir '*.md' excluye .py", not ok4)
ok5, _ = _deberia_incluir(mk("README.md"), exts, ["*.md"], None, Path("."))
check("--incluir '*.md' incluye .md", ok5)

ok6, _ = _deberia_incluir(mk("tests/test_x.py"), exts, None, ["tests/*"], Path("."))
check("--excluir 'tests/*' excluye test", not ok6)
ok7, _ = _deberia_incluir(mk("src/app.py"), exts, None, ["tests/*"], Path("."))
check("--excluir 'tests/*' mantiene src", ok7)


# ── `_archivos_en_directorio`: salta dirs excluidos ───────────────────────────

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("x", encoding="utf-8")
    (root / "vendor").mkdir()
    (root / "vendor" / "b.bin").write_text("bin", encoding="utf-8")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("x", encoding="utf-8")
    archivos = _archivos_en_directorio(root)
    nombres = [p.name for p in archivos]
    check("salta .git y vendor", ("a.py" in nombres) and ("config" not in nombres) and ("b.bin" not in nombres))


# ── `_concatenar_archivos`: cabeceras y límite de bytes ───────────────────────

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    f1 = root / "a.py"; f1.write_text("def f():\n    pass\n", encoding="utf-8")
    f2 = root / "b.md"; f2.write_text("# Doc", encoding="utf-8")
    texto, nbytes, detalle = _concatenar_archivos([f1, f2], root, 100000)
    check("incluye cabecera de archivo a.py", "=== ARCHIVO: a.py ===" in texto)
    check("incluye cabecera de archivo b.md", "=== ARCHIVO: b.md ===" in texto)
    check("concatenación no vacía", len(texto) > 0 and nbytes > 0)

    # Límite de bytes: un archivo que excedería se excluye con razon
    texto2, nbytes2, detalle2 = _concatenar_archivos([f1], root, 1)
    check("límite de bytes aplicado (archivo excluido)",
          nbytes2 == 0 and any(d["incluir"] is False for d in detalle2))


# ── `_escaneo_peligro_sistema` (perfil referencia_codigo) ─────────────────────
# Imports de librerías/proyecto son legítimos en API; solo bloquea sistema.

check("import de paquete/proyecto es seguro (API)",
      _escaneo_peligro_sistema("from itsdangerous import Signer\ns = Signer('k')") is None)
check("import de librería stdlib es seguro (API)",
      _escaneo_peligro_sistema("import hashlib\nh = hashlib.sha256(b'x')") is None)
check("import de os bloqueado (peligro sistema)",
      _escaneo_peligro_sistema("import os\nos.system('rm -rf /')") is not None)
check("import from subprocess bloqueado (peligro sistema)",
      _escaneo_peligro_sistema("from subprocess import run\nrun(['ls'])") is not None)
check("llamada a eval bloqueada (peligro sistema)",
      _escaneo_peligro_sistema("x = eval('1+1')") is not None)
check("llamada a open bloqueada (peligro sistema)",
      _escaneo_peligro_sistema("f = open('secret.txt')") is not None)

# Diferencia clave entre perfiles:
# En perfil libro, cualquier import fuera de math/sympy/fractions es inseguro;
# en perfil código, import de librería es seguro.
check("perfil libro: import de proyecto SÍ es inseguro",
      _escaneo_seguridad("from itsdangerous import Signer") is not None)
check("perfil libro: import de hashlib SÍ es inseguro",
      _escaneo_seguridad("import hashlib") is not None)


# ── `_extraer_bloques`: reconoce bloques ```python ────────────────────────────

texto_bloques = """# titulo

```python
from itsdangerous import Signer
```

parrafo

```python
def firma(x):
    ...
```
"""
bloques = _extraer_bloques(texto_bloques)
check("extrae 2 bloques python", len(bloques) == 2)
check("primer bloque es itsdangerous", "itsdangerous" in bloques[0]["src"])
check("segundo bloque (firma incompleta) extraído", "def firma" in bloques[1]["src"])
check("bloque con lenguaje no python se ignora",
      len(_extraer_bloques("```bash\necho hola\n```")) == 0)


print()
if FALLOS:
    print(f"  {len(FALLOS)} tests FALLARON: {FALLOS}")
    sys.exit(1)
print("  Todos los tests pasaron (0 créditos).")
sys.exit(0)
