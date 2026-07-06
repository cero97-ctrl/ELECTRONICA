#!/usr/bin/env python3
import os
import sys
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Cargar variables de entorno y añadir root al path
project_root = os.path.dirname(os.path.abspath(__file__))
load_dotenv(os.path.join(project_root, ".env"))
sys.path.append(project_root)

from execution.system_control import apagar_equipo

# Inicializar el servidor MCP de FastMCP
mcp = FastMCP("System Control Server")

@mcp.tool()
def apagar_sistema() -> str:
    """
    Apaga el ordenador local inmediatamente.
    """
    resultado = apagar_equipo()
    if resultado["status"] == "success":
        return f"✅ {resultado['message']}"
    else:
        return f"❌ {resultado['message']}"

if __name__ == "__main__":
    mcp.run()
