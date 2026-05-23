#!/usr/bin/env python
import os
import argparse
import markdown
import pdfkit

def convert_doc_to_pdf(md_path):
    if not os.path.exists(md_path):
        print(f"Error: El archivo '{md_path}' no existe.")
        return

    if not md_path.lower().endswith('.md'):
        print(f"Error: El archivo '{md_path}' no parece ser un archivo Markdown (.md).")
        return

    # Definir el nombre del archivo PDF de salida
    pdf_path = os.path.splitext(md_path)[0] + '.pdf'
    
    print(f"Procesando: {md_path} -> {pdf_path}")
    
    try:
        # 1. Leer el contenido Markdown
        with open(md_path, 'r', encoding='utf-8') as f:
            md_text = f.read()
        
        # 2. Convertir Markdown a HTML con extensiones útiles
        html_body = markdown.markdown(md_text, extensions=['fenced_code', 'tables'])
        
        # 3. Envolver el HTML con una plantilla básica y estilos CSS
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; margin: 2em; }}
                pre {{ background-color: #f4f4f4; padding: 10px; border-radius: 5px; overflow-x: auto; }}
                code {{ font-family: monospace; }}
                table {{ border-collapse: collapse; width: 100%; margin-bottom: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            {html_body}
        </body>
        </html>
        """
        
        # 4. Generar el PDF
        pdfkit.from_string(html_content, pdf_path, options={"enable-local-file-access": ""})
        print("  ✓ Conversión exitosa.")
        
    except Exception as e:
        print(f"  x Error al convertir {md_path}: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Convierte un archivo Markdown a PDF.")
    parser.add_argument("md_file", help="Ruta al archivo Markdown (.md) a convertir")
    
    args = parser.parse_args()
    
    convert_doc_to_pdf(args.md_file)