#!/usr/bin/env python3
import argparse
from pypdf import PdfWriter

def main():
    parser = argparse.ArgumentParser(description="Une múltiples archivos PDF en uno solo.")
    parser.add_argument("inputs", nargs='+', help="Rutas de los archivos PDF a unir")
    parser.add_argument("-o", "--output", default="merged_output.pdf", help="Ruta del archivo PDF de salida (por defecto: merged_output.pdf)")
    
    args = parser.parse_args()

    merger = PdfWriter()

    for pdf in args.inputs:
        merger.append(pdf)

    merger.write(args.output)
    merger.close()

    print(f"Los archivos PDF se han unido exitosamente en: {args.output}")

if __name__ == "__main__":
    main()