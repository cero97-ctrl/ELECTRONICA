# Paquete del estudiante — Semana 02

**Ciberseguridad Aplicada · Fase 1 · Criptografía aplicada y gestión de secretos**

Material listo para entregar a los cuatro grupos. Los PDF `01` a `07` se generan
desde `cursos/CYBERSEGURIDAD/curso.yaml` y son copias de los artefactos
canónicos: **no se editan a mano**. El aviso `00` es un entregable puntual.

## Contenido

| Archivo | Para qué sirve |
| --- | --- |
| `00_mensaje_whatsapp_semana_02.pdf` | Aviso para enviar por WhatsApp: enlace al paquete, los 7 PDF y reglas de entrega. |
| `01_instrucciones_semana_02.pdf` | Instrucciones paso a paso, rol de cada grupo, qué se entrega y cómo se corrige. |
| `02_practica_02.pdf` | Enunciado de la práctica «Caja de herramientas criptográficas». |
| `03_rol_rojo_grupo_1.pdf` | Ejemplo de trabajo del rol Rojo: cifrar, firmar y romper la integridad. |
| `04_rol_azul_grupo_2.pdf` | Ejemplo del rol Azul: diagnosticar TLS y elegir parámetros con medición. |
| `05_rol_purpura_grupo_3.pdf` | Ejemplo del rol Púrpura: instrumentar las operaciones criptográficas. |
| `06_legal_reporte_grupo_4.pdf` | Ejemplo del rol Legal y reporte: custodia de secretos y admisibilidad. |
| `07_guia_teorica_02.pdf` | Guía de estudio de los cinco temas de la semana (AES-GCM, RSA/ECC, hash/HMAC/KDF, TLS y secretos). |

El aviso `00_mensaje_whatsapp_semana_02.{tex,pdf}` transcribe el mensaje aprobado
para el grupo; es el único archivo de la carpeta que no se deriva de `curso.yaml`.

Los cuatro ejemplos son **modelos de trabajo**, no la entrega: cambian el énfasis
según el rol, pero todos los grupos resuelven la misma práctica en su propio
repositorio y laboratorio.

## Antes de empezar

1. Comprobar que el repositorio privado del grupo tiene la carpeta `semana_02/`.
2. Leer la retroalimentación de la semana 01 y corregir lo pendiente.
3. Tener instalados `openssl`, `sha256sum` y el módulo `cryptography` de Python.
4. Confirmar que el laboratorio local arranca y que sus servicios responden.

## Entrega y corte

- **Corte:** domingo 23:59 de la semana correspondiente. A partir de la semana 02
  la fecha **sí cuenta**: lo que se suba después no se corrige (`evaluar_corte: true`).
- **Commit:** uno por entrega, con mensaje `semana 02: <entregable>`.

Estructura obligatoria dentro del repositorio del grupo:

```
README.md                 integrantes, roles y tabla de semanas entregadas
semana_02/informe.md      o informe.pdf con el entregable
semana_02/scripts/        código con type hints y docstrings
semana_02/evidencia/      salidas reales, capturas y hashes anonimizados
semana_02/README.md       resumen de lo hecho y de lo que no se pudo verificar
```

## Reglas que se verifican al corregir

- Nada de secretos, tokens ni contraseñas en el repositorio: las claves van en
  `.env` ignorado.
- Nada de imágenes de disco, muestras de malware ni binarios: solo hashes y enlaces.
- Evidencia anonimizada: sin datos personales de terceros ni credenciales reales.
- Cada hallazgo lleva su salida cruda o su hash, que permiten reproducirlo.
- La práctica cuenta como entregada solo si está en el repositorio antes del corte.

## Regeneración

Desde la raíz del repo:

```bash
python3 flujo_instrucciones_semana.py --curso cursos/CYBERSEGURIDAD/curso.yaml --semana 2
for g in 1 2 3 4; do \
  python3 flujo_instrucciones_semana.py --curso cursos/CYBERSEGURIDAD/curso.yaml --semana 2 --grupo $g; \
done
python3 flujo_disenar_curso.py --curso cursos/CYBERSEGURIDAD/curso.yaml --solo practicas
python3 flujo_guia_teorica.py --curso cursos/CYBERSEGURIDAD/curso.yaml --semana 2
```

Después se copian los PDF a esta carpeta. Las infografías divulgativas por rol
viven en `docs/INFOGRAFIAS/SEM_2/` (carpeta local, excluida de git) y se comparten
por el aula virtual, nunca con `git add -f`.
