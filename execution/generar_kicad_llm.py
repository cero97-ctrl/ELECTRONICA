#!/usr/bin/env python3
"""
generar_kicad_llm.py — Generador de esquemáticos KiCAD 8.0.9 utilizando un modelo LLM.
Toma el JSON de netlist y usa la LLM para generar el código S-Expression del esquemático.
"""

import argparse
import json
import os
import sys
import re
from pathlib import Path
from dotenv import load_dotenv

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

def generar_con_llm(netlist_json: str, modelo: str, api_backend: str, api_key: str) -> str:
    system_instruction = (
        "Eres un experto ingeniero en electrónica y usuario avanzado de KiCAD 8. "
        "A continuación recibirás un netlist en formato JSON. Tu tarea es generar el código "
        "fuente completo de un archivo `.kicad_sch` (formato S-Expression, version 20231120) "
        "que corresponda a ese netlist. Responde ÚNICAMENTE con el código del archivo, sin "
        "formato markdown extra (o si usas formato, que sea dentro de ```kicad ... ```), "
        "y no añadas explicaciones adicionales. No incluyas texto fuera del bloque de código."
    )
    prompt = f"Genera el archivo .kicad_sch completo para este netlist:\n\n{netlist_json}"

    if api_backend in ["groq", "openrouter"]:
        if OpenAI is None:
            raise ImportError("Paquete 'openai' no instalado.")
        base_url = "https://api.groq.com/openai/v1" if api_backend == "groq" else "https://openrouter.ai/api/v1"
        client = OpenAI(api_key=api_key, base_url=base_url)
        response = client.chat.completions.create(
            model=modelo,
            messages=[
                {"role": "system", "content": system_instruction},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=8192
        )
        if not response.choices:
            raise RuntimeError("Respuesta vacía del LLM.")
        return response.choices[0].message.content
        
    elif api_backend == "gemini":
        try:
            from google import genai
            client_g = genai.Client(api_key=api_key)
            response = client_g.models.generate_content(
                model=modelo,
                contents=system_instruction + "\n\n" + prompt
            )
            return response.text
        except ImportError:
            import google.generativeai as genai_legacy
            genai_legacy.configure(api_key=api_key)
            model_g = genai_legacy.GenerativeModel(model_name=modelo)
            response = model_g.generate_content(system_instruction + "\n\n" + prompt)
            return response.text
    else:
        raise ValueError(f"Backend no soportado: {api_backend}")

def extract_code(text: str) -> str:
    match = re.search(r"```[a-zA-Z0-9_-]*\s*\n(.*?)\n```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    return text.strip()

def main():
    load_dotenv()
    parser = argparse.ArgumentParser(description="Genera archivo .kicad_sch desde Netlist JSON usando un LLM.")
    parser.add_argument("--json", required=True, help="Ruta al JSON del Netlist")
    parser.add_argument("--output", required=True, help="Ruta de salida para el .kicad_sch")
    parser.add_argument("--modelo", default="gemini-2.5-flash", help="Modelo a utilizar")
    parser.add_argument("--api-backend", default="gemini", choices=["gemini", "openrouter", "groq"])
    args = parser.parse_args()

    json_path = Path(args.json)
    out_path = Path(args.output)
    
    if not json_path.exists():
        print(json.dumps({"status": "error", "message": f"Archivo no encontrado: {json_path}"}))
        sys.exit(1)
        
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            netlist = json.load(f)
            
        if "analisis" in netlist:
            netlist = netlist["analisis"]

        if args.api_backend == "groq":
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                try:
                    with open(Path(__file__).parent.parent / ".groq_api_key", "r") as fk:
                        api_key = fk.read().strip()
                except Exception:
                    pass
        elif args.api_backend == "openrouter":
            api_key = os.getenv("OPENROUTER_API_KEY")
        else:
            api_key = os.getenv("GOOGLE_API_KEY")

        if not api_key:
            print(json.dumps({"status": "error", "message": f"API key no encontrada para {args.api_backend}"}))
            sys.exit(1)

        raw_text = generar_con_llm(json.dumps(netlist, indent=2), args.modelo, args.api_backend, api_key)
        code = extract_code(raw_text)
        
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(code + "\n")
            
        print(json.dumps({"status": "ok", "file": str(out_path)}))
        sys.exit(0)
    except Exception as e:
        print(json.dumps({"status": "error", "message": str(e)}))
        sys.exit(1)

if __name__ == "__main__":
    main()
