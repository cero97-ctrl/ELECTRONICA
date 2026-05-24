#!/usr/bin/env python3
import os
import argparse

# Extensiones que deseamos CONSERVAR
KEEP_EXTENSIONS = [".tex", ".pdf", ".py"]

def clean_latex_aux_files(directory):
    if not os.path.exists(directory):
        print(f"Error: El directorio no existe -> {directory}")
        return

    print(f"Buscando archivos para eliminar recursivamente (conservando solo .tex, .pdf y .py) en:\n{directory}\n")
    deleted_count = 0

    for root, _, files in os.walk(directory):
        for filename in files:
            filepath = os.path.join(root, filename)
            
            if os.path.isfile(filepath):
                _, ext = os.path.splitext(filename)
                
                if ext.lower() not in KEEP_EXTENSIONS:
                    try:
                        os.remove(filepath)
                        print(f"Eliminado: {filepath}")
                        deleted_count += 1
                    except Exception as e:
                        print(f"Error al intentar eliminar {filepath}: {e}")

    print(f"\n¡Limpieza completada! Se eliminaron {deleted_count} archivos.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Limpia archivos auxiliares de LaTeX en un directorio específico.")
    parser.add_argument("directory", help="Ruta al directorio objetivo donde se realizará la limpieza")
    
    args = parser.parse_args()
    
    clean_latex_aux_files(args.directory)