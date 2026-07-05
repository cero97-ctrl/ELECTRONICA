#!/bin/bash

# Script para gestionar el contenedor de Waydroid
# Debe ejecutarse en sistemas con systemd

SERVICE_NAME="waydroid-container.service"

echo "========================================="
echo "        Gestor de Waydroid (LXC)         "
echo "========================================="

# Mostrar el estado actual
echo -n "Estado actual del Contenedor: "
if systemctl is-active --quiet $SERVICE_NAME; then
    echo -e "\033[32mACTIVO (Corriendo)\033[0m"
else
    echo -e "\033[31mDETENIDO\033[0m"
fi

echo "-----------------------------------------"
echo "¿Qué deseas hacer?"
echo "1) Start (Iniciar el contenedor)"
echo "2) Stop (Detener el contenedor y la sesión)"
echo "3) Restart (Reiniciar el contenedor)"
echo "4) Status (Ver estado detallado)"
echo "5) Weston (Iniciar compositor Wayland)"
echo "6) Salir"
echo "-----------------------------------------"

read -p "Elige una opción (1-6): " opcion

case $opcion in
    1)
        echo "Iniciando el contenedor de Waydroid..."
        sudo systemctl start $SERVICE_NAME
        echo "¡Contenedor iniciado! (Usa 'waydroid session start' para lanzar la UI)"
        ;;
    2)
        echo "Deteniendo la sesión de Waydroid (si existe)..."
        waydroid session stop 2>/dev/null
        echo "Deteniendo el contenedor de Waydroid..."
        sudo systemctl stop $SERVICE_NAME
        echo "¡Contenedor detenido!"
        ;;
    3)
        echo "Deteniendo la sesión de Waydroid (si existe)..."
        waydroid session stop 2>/dev/null
        echo "Reiniciando el contenedor de Waydroid..."
        sudo systemctl restart $SERVICE_NAME
        echo "¡Contenedor reiniciado!"
        ;;
    4)
        echo "Mostrando el estado detallado (presiona 'q' para salir):"
        systemctl status $SERVICE_NAME
        ;;
    5)
        echo "Iniciando compositor Weston..."
        weston
        ;;
    6)
        echo "Saliendo..."
        exit 0
        ;;
    *)
        echo "Opción no válida."
        exit 1
        ;;
esac
