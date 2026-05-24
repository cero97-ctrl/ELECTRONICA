#!/usr/bin/env python
import os
import sys
import glob
import argparse

parser = argparse.ArgumentParser(description="Elimina la cadena CIRC_DISP_ELECT del nombre de los archivos.")
parser.add_argument("folder_path", help="Ruta de la carpeta que contiene los archivos a renombrar")
args = parser.parse_args()

folder_path = args.folder_path
if not os.path.isdir(folder_path):
    print(f"Error: El directorio '{folder_path}' no existe.")
    sys.exit(1)

# Extensiones a procesar
extensions = ["*.tex", "*.pdf", "*.text"]

# Cadenas de texto a eliminar (cubriendo guiones bajos y medios)
strings_to_remove = ["-CIRC-DISP-ELECT", "_CIRC_DISP_ELECT", "CIRC_DISP_ELECT", "CIRC-DISP-ELECT"]

archivos = []
for ext in extensions:
    archivos.extend(glob.glob(os.path.join(folder_path, ext)))

renombrados = 0

for ruta_archivo in archivos:
    directorio = os.path.dirname(ruta_archivo)
    nombre_original = os.path.basename(ruta_archivo)
    nuevo_nombre = nombre_original
    
    for cadena in strings_to_remove:
        nuevo_nombre = nuevo_nombre.replace(cadena, "")
        
    # Limpieza de guiones colgados justo antes de la extensión (ej: "archivo-.pdf" -> "archivo.pdf")
    nuevo_nombre = nuevo_nombre.replace("-.pdf", ".pdf").replace("-.tex", ".tex").replace("_.pdf", ".pdf").replace("_.tex", ".tex")
    
    if nuevo_nombre != nombre_original:
        nueva_ruta = os.path.join(directorio, nuevo_nombre)
        os.rename(ruta_archivo, nueva_ruta)
        print(f"Renombrado: {nombre_original} -> {nuevo_nombre}")
        renombrados += 1

print(f"\nProceso completado. Se renombraron {renombrados} archivos.")